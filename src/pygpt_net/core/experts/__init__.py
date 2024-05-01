#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://pygpt.net                         #
# GitHub:  https://github.com/szczyglis-dev/py-gpt   #
# MIT License                                        #
# Created By  : Marcin Szczygliński                  #
# Updated Date: 2024.05.01 17:00:00                  #
# ================================================== #

from pygpt_net.core.bridge import BridgeContext
from pygpt_net.core.dispatcher import Event
from pygpt_net.item.ctx import CtxItem
from pygpt_net.item.preset import PresetItem


class Experts:
    def __init__(self, window=None):
        """
        Experts core

        :param window: Window instance
        """
        self.window = window

    def get_expert(self, id: str) -> PresetItem:
        """
        Get expert by id

        :param id: expert id
        :return: expert item or None
        """
        return self.window.core.presets.get_by_id("expert", id)

    def get_experts(self) -> dict:
        """
        Get experts

        :return: experts dict
        """
        experts = {}
        presets = self.window.core.presets.get_by_mode("expert")

        # mode: agent
        if self.window.controller.agent.enabled():
            agents = self.window.core.presets.get_by_mode("agent")
            agent = self.window.core.config.get('preset')
            if agent is not None:
                if agent in agents:
                    for uuid in agents[agent].experts:
                        expert = self.window.core.presets.get_by_uuid(uuid)
                        if expert is not None:
                            id = expert.filename
                            experts[id] = expert.name
        # mode: expert
        else:
            for k in presets:
                if k.startswith("current."):
                    continue
                if not presets[k].enabled:
                    continue
                experts[k] = presets[k].name
        return experts

    def get_prompt(self) -> str:
        """
        Get prompt from expert

        :return: prompt string with experts list
        """
        prompt = self.window.core.config.get('prompt.expert')
        experts = self.get_experts()
        experts_list = []
        for k in experts:
            if k.startswith("current."): # skip current presets
                continue
            experts_list.append(" - " + str(k) + ": " + str(experts[k]))
        prompt = prompt.replace("{presets}", "\n".join(experts_list))
        return prompt

    def extract_mentions(self, ctx: CtxItem) -> dict:
        """
        Extract mentions from context

        :param ctx: context item
        :return: dict with mentions
        """
        ids = self.get_experts().keys()
        if not ids:
            return {}
        cmds = self.window.core.command.extract_cmds(ctx.output)
        if len(cmds) > 0:
            ctx.cmds = cmds  # append commands to ctx
        else:
            return {}
        commands = self.window.controller.plugins.from_commands(cmds)  # pack to execution list
        allowed_cmds = ["expert_call"]
        is_cmd = False
        my_commands = []
        mentions = {}
        for item in commands:
            if item["cmd"] in allowed_cmds:
                my_commands.append(item)
                is_cmd = True
        if not is_cmd:
            return {}
        for item in my_commands:
            try:
                if item["cmd"] == "expert_call":
                    if "params" not in item:
                        continue
                    if "id" not in item["params"] or "query" not in item["params"]:
                        continue
                    id = item["params"]["id"]
                    if id not in ids:
                        continue
                    query = item["params"]["query"]
                    mentions[id] = query
            except Exception as e:
                self.window.core.debug.error(e)
                return {}
        return mentions

    def reply(self, ctx: CtxItem):
        """
        Resend response to master expert

        :param ctx: context item
        :return: response text
        """
        if self.window.controller.agent.experts.stopped():
            return
        internal = False
        if self.window.controller.agent.enabled():  # hide in agent mode
            internal = True
        if ctx.output.strip() != "":
            response = ctx.output
        else:
            response = ctx.input
        self.window.controller.chat.input.send(
            "Result from expert:\n\n" + str(response),
            force=True,
            reply=True,
            internal=internal,
            prev_ctx=ctx,
        )

    def call(
            self,
            master_ctx: CtxItem,
            expert_id: str,
            text: str
    ):
        """
        Call expert

        :param master_ctx: master context
        :param expert_id: expert id (preset ID)
        :param text: input text (master prompt)
        """
        if self.window.controller.agent.experts.stopped():
            return
        # get or create children meta
        slave = self.window.core.ctx.get_or_create_slave_meta(master_ctx, expert_id)
        expert = self.get_expert(expert_id)
        reply = True

        mode = self.window.core.config.get("experts.mode")
        base_mode = mode
        model = expert.model
        user_name = expert.name
        ai_name = expert.name
        sys_prompt = expert.prompt
        model_data = self.window.core.models.get(model)
        files = []
        file_ids = []
        functions = []
        tools_outputs = []
        max_tokens = self.window.core.config.get('max_output_tokens')
        stream_mode = self.window.core.config.get('stream')

        hidden = False
        internal = False
        if self.window.controller.agent.enabled():  # hide in agent mode
            internal = False
            hidden = True

        # create slave item
        ctx = CtxItem()
        ctx.meta_id = slave.id
        ctx.internal = internal
        ctx.hidden = hidden
        ctx.current = True  # mark as current context item
        ctx.mode = mode  # store current selected mode (not inline changed)
        ctx.model = model  # store model list key, not real model id
        ctx.set_input(text, user_name)
        ctx.set_output(None, str(ai_name))
        ctx.sub_call = True  # mark as sub-call

        # render: begin
        self.window.controller.chat.render.begin(stream=stream_mode)
        self.window.core.ctx.provider.append_item(slave, ctx)  # to slave meta

        # build sys prompt
        sys_prompt_raw = sys_prompt  # store raw prompt
        event = Event(Event.PRE_PROMPT, {
            'mode': mode,
            'value': sys_prompt,
        })
        self.window.core.dispatcher.dispatch(event)
        sys_prompt = event.data['value']
        sys_prompt = self.window.core.prompt.prepare_sys_prompt(
            mode,
            sys_prompt,
            ctx,
            reply,
            internal,
        )

        # call bridge
        history = self.window.core.ctx.all(meta_id=slave.id)  # get all history for slave ctx
        bridge_context = BridgeContext(
            ctx=ctx,
            history=history,
            mode=mode,
            parent_mode=base_mode,
            model=model_data,
            system_prompt=sys_prompt,
            system_prompt_raw=sys_prompt_raw,
            prompt=text,
            stream=stream_mode,
            attachments=files,
            file_ids=file_ids,
            assistant_id=self.window.core.config.get('assistant'),
            idx=self.window.controller.idx.current_idx,
            idx_raw=self.window.core.config.get('llama.idx.raw'),
            external_functions=functions,
            tools_outputs=tools_outputs,
            max_tokens=max_tokens,
        )
        self.window.controller.chat.common.lock_input()  # lock input
        result = self.window.core.bridge.call(
            context=bridge_context,
        )
        if not result:
            return

        # handle output
        ctx.current = False  # reset current state
        self.window.core.ctx.update_item(ctx)
        ctx.from_previous()  # append previous result if exists
        self.window.controller.chat.output.handle(
            ctx,
            mode,
            stream_mode,
        )
        ctx.clear_reply()  # reset results
        self.window.controller.chat.output.handle_cmd(ctx)  # handle cmds
        ctx.from_previous()  # append previous result again before save
        self.window.core.ctx.update_item(ctx)  # update ctx in DB

        # if commands reply here, then stop
        if ctx.reply:
            return

        # send slave expert response to master expert
        self.window.controller.chat.input.send(
            "@"+expert_id+" says:\n\n" + str(ctx.output),
            force=True,
            reply=False,
            internal=False,
            prev_ctx=ctx,
        )

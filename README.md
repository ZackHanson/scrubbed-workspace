# scrubbed-workspace

**This README page is for YOU, and the SETUP-PLAYBOOK is for the AI agent.**

Scrubbed Workspace helps you use AI in colaboration with your email.
What you'll have:
1. A workspace your AI can read that contains only processed email copies.
2. A private place to review messages the setup doesn't deem fully confidant in.
3. A way to check, pause, and resume the workspace.

## Start here

1. Open Claude or your preferred coding agent. It needs to edit files and run
   commands on your computer. A chat-only model can help you get that set up first.
2. Paste the prompt below.
3. Answer its questions and follow the local sign-in or installation steps it
   explains. At the end, have it demonstrate the workspace and show you how to use it.

You do not need to install the required software or models beforehand. Keep
private email, passwords and API keys out of the chat.

do not give it blanket administrator access or disable your computer's security protections.
You can pause setup at any time.

### Returning to an existing setup

1. Open your coding agent and select the same project folder you used before.
2. Paste this message:

   > Read SETUP-PLAYBOOK.md and check what has already been set up in this folder
   > and on my computer. Look for the setup receipt (the record of previous setup
   > steps and checks), and verify what is installed and working. Explain what
   > still needs to be done, then continue from there. Preserve my existing work.
   > If there is no receipt, inspect what is here before making changes. Do not
   > start over or turn email processing back on automatically.

You do not need to create another folder or repeat the first-time setup prompt.

### Prompt to paste

```text
Read SETUP-PLAYBOOK.md and follow it to build, install and test my own complete
scrubbed workspace in this project folder. Assume only my operating system is
installed. Inspect my computer, choose suitable local models and software, and
install what is missing.

First explain your plan in plain language and ask only for decisions you cannot
infer or inspect. Do the setup work yourself where your tools allow. When you
need my input or a
manual step, explain one action at a time, tell me how to check that it worked,
and wait for that result before continuing dependent steps. Keep private email and
credentials out of this chat; help me enter them through secure local setup.

Finish with a working workspace, a demonstration and simple operating instructions.
If you cannot work on my computer yet, first help me get a coding agent with the
local access needed to do this.
```

# scrubbed-workspace

A setup playbook for building your own workspace from locally scrubbed email.
Start here, then give the playbook to your coding agent.

## Start here

1. Open Claude or your preferred coding agent. It needs to edit files and run
   commands on your computer. A chat-only model can help you get that set up first.
2. Create the folder **on your computer**. On Windows, use File Explorer to create
   `C:\Users\YOUR-USERNAME\Projects\scrubbed-workspace`, replacing `YOUR-USERNAME`
   with your Windows username. On Mac/Linux, use `~/Projects/scrubbed-workspace`.
3. In your coding agent, choose its option to open a local folder and select that
   exact folder. Use the local-folder picker, rather than just naming a chat project.
   Reuse this folder when you return to setup later.
4. Save [SETUP-PLAYBOOK.md](SETUP-PLAYBOOK.md) in that folder so the agent can read it.
5. Start a chat in that project and paste the prompt below.
6. Answer its questions and follow the local sign-in or installation steps it
   explains. At the end, have it demonstrate the workspace and show you how to
   start, pause and use it.

You do not need to install the required software or models beforehand. Keep
private email, passwords and API keys out of the chat.

### Prompt to paste

```text
Read SETUP-PLAYBOOK.md and follow it to build, install and test my own complete
scrubbed workspace in this project folder. Assume only my operating system is
installed. Inspect my computer, choose suitable local models and software, and
install what is missing.

Do the setup work yourself where your tools allow. When you need my input or a
manual step, explain what I need to do, one step at a time. Keep private email and
credentials out of this chat; help me enter them through secure local setup.

Finish with a working workspace, a demonstration and simple operating instructions.
If you cannot work on my computer yet, first help me get a coding agent with the
local access needed to do this.
```

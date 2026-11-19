# scrubbed-workspace

A setup playbook for building your own workspace from locally scrubbed email.
Start here, then give the playbook to your coding agent.

The playbook requires safety checks before live use; it cannot guarantee that
an agent-built application is safe or that automated redaction catches everything.
Keep live processing disabled until the installed system passes its checks and
you understand its remaining risks. Use your organization's approved process for
confidential or regulated information.

## Start here

1. Open Claude or your preferred coding agent. It needs to edit files and run
   commands on your computer. A chat-only model can help you get that set up first.
2. For first setup, create an **empty folder on your computer**.
   On Windows, use File Explorer to create
   `C:\Users\YOUR-USERNAME\Projects\scrubbed-workspace`, replacing `YOUR-USERNAME`
   with your Windows username. On Mac/Linux, use `~/Projects/scrubbed-workspace`.
3. In your coding agent, choose its option to open a local folder and select that
   exact folder. Use the local-folder picker, rather than just naming a chat project.
   Keep private email and runtime data outside this folder.
4. Open [SETUP-PLAYBOOK.md](SETUP-PLAYBOOK.md) on GitHub and use **Download raw
   file** (the download button in the file toolbar). Alternatively, choose **Raw**
   and save that raw text. Save it as `SETUP-PLAYBOOK.md` in your new project folder.
   Do not use **Save page as** on GitHub's rendered file page: that saves an HTML
   webpage. Open the saved file in a text editor and check that it starts with
   `# Build and install` and includes a **Playbook version**, rather than HTML.
5. Start a chat in that project and paste the prompt below.
6. Answer its questions and follow the local sign-in or installation steps it
   explains. At the end, have it demonstrate the workspace and show you how to
   start, pause and use it.

You do not need to install the required software or models beforehand. Keep
private email, passwords and API keys out of the chat.
The agent should explain any specific installation step needing administrator approval;
do not give it blanket administrator access or disable your computer's security protections.
You can pause setup at any time.

### Returning to an existing setup

Open the same application folder. Ask the agent to read the playbook and existing
setup receipt, verify the installed source, configuration and completed checks,
and resume the first unfinished dependency. Do not start over, overwrite an
installation or reactivate processing just because you reopened the folder.
If the folder already contains work but has no receipt, have the agent inspect
and preserve it before proposing how to continue.

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

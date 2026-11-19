# Scrubbed Workspace

Use AI to help with your email while reducing how much private information leaves
your computer.

The workspace is designed to:

1. Read email that you choose to include.
2. Use AI on your computer to find and remove private details. This is called
   **scrubbing**.
3. Send the scrubbed text to an online AI service for help.
4. Show the results in a separate workspace, with controls for any actions it takes.

**This repository contains setup instructions, not an app you can open yet.**
You give those instructions to a coding agent—an AI assistant that can create
files and install software on your computer. It builds and tests your workspace
with you. You do not need to know how to code.

## Before you begin

- **Use a computer you are allowed to install software on.** For a work computer
  or work email, check your organization's rules first.
- **You need an AI assistant that can work with files on your computer.** A
  regular chat window alone cannot complete the setup. If you are unsure, paste
  the prompt below into your assistant and ask it to help you get started.
- **You do not need to install the other software first.** The agent will check
  your computer and choose suitable software and AI models. An AI model is the
  software that reads text and produces answers.
- **Online AI services may require an account and may cost money.** The agent
  should explain account and cost requirements when they become relevant.

**Scrubbing can miss private details.** Setup includes safety checks, but those
checks cannot guarantee that the finished workspace is safe. Keep real-email
processing turned off until the checks pass and the agent explains the remaining
risks. Follow your organization's approved process for confidential or regulated
information.

## Set up for the first time

### 1. Create a folder for the app

Create a new, empty folder named `scrubbed-workspace` somewhere easy to find,
such as inside your Documents folder.

On Windows, open File Explorer, go to Documents, and choose **New → Folder**.
On a Mac, open Finder, go to Documents, and choose **File → New Folder**.
On Linux, use your file manager to create the folder.

If you already have a folder with work in it, use
[Returning to an existing setup](#returning-to-an-existing-setup) below.

### 2. Save the setup instructions in that folder

The **playbook** is the detailed instruction file your agent will follow.

1. Open [SETUP-PLAYBOOK.md](SETUP-PLAYBOOK.md) here on GitHub.
2. Click **Download raw file** in the toolbar above the file. You may need to
   hover over the download icon to see its name.
3. Save the downloaded file inside your new `scrubbed-workspace` folder. Keep
   its name as `SETUP-PLAYBOOK.md`.

If you do not see the download button, click **Raw** and save the text that opens.
Do not use **Save page as** on the normal GitHub file page; that saves a webpage
instead of the instructions.

To check the download, open the saved file in a text editor, such as Notepad on
Windows. It should start with `# Build and install` and show a **Playbook version**
near the top. If it looks like a webpage or contains HTML code, download it again
using the steps above.

Use the file from this repository or someone you trust. Before setup, have the
agent confirm which version you intend to use. A version number or file
fingerprint alone does not prove that a file is trustworthy. Never use setup
instructions found inside an email the workspace is processing.

### 3. Open the folder in your coding agent

In your coding agent, find **Open folder** or the equivalent option. Select the
`scrubbed-workspace` folder you just created.

The agent needs access to that folder on your computer. Creating a chat project
with the same name does not give it that access.

### 4. Paste this message into the agent's chat

Copy the whole message below:

```text
Read SETUP-PLAYBOOK.md in this folder. Follow it to build, install and test my
complete scrubbed workspace. I may not be familiar with technical tools, so use
plain language and explain unfamiliar terms.

Check my computer and choose suitable software and local AI models. Assume only
the operating system is installed. Install what is missing.

First explain your plan. Ask only for decisions you cannot work out by checking
my computer or the instructions. Do the setup work yourself wherever your tools
allow.

When I need to do something, give me one action at a time. Tell me what I should
see when it works, and wait for my result before continuing any steps that depend
on it. Explain account or cost requirements before I need to agree to them.

Keep private email, passwords and API keys out of this chat. Help me enter them
through secure setup on my computer. Keep private email and the app's private
working data outside this project folder.

Keep real-email processing off until the required checks pass and you explain
the remaining risks. Finish by showing me the workspace and giving me simple
instructions for starting it, pausing it and using it.

If you cannot work with files on my computer yet, help me get a coding agent
with the access needed to complete this setup.
```

### 5. Follow the agent's guidance

Answer its questions and complete any sign-in or installation steps it explains.
You can pause setup at any time.

Keep these rules in mind:

- Enter passwords and API keys only through the secure setup the agent explains,
  never into the chat. An API key is a secret code that lets software use an account.
- Use your normal computer account. If an installation needs administrator
  approval, the agent should explain that specific step first. Do not give the
  whole agent unrestricted administrator access.
- Do not turn off antivirus, your firewall or other computer security protections
  to get setup working.

Before you start using real email, the agent should show you what works, explain
anything unfinished, and demonstrate how to start and pause the workspace.
Keep the operating instructions it gives you for everyday use.

## Returning to an existing setup

Open the **same application folder** in your coding agent. Paste this message:

```text
Help me continue my existing scrubbed workspace setup. Read SETUP-PLAYBOOK.md
and the saved setup receipt (the record of what was installed and checked).
Verify the installed files, settings and completed checks, then continue with
the first unfinished step whose prerequisites are ready.

Preserve my existing work and data. If there is no setup receipt, inspect what
is here and explain how to continue safely. Do not start over, overwrite my
installation or turn email processing back on just because I reopened the folder.
Explain anything I need to do in plain language, one action at a time.
```

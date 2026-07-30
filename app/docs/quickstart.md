# AIC-ADE Quick Start Guide

## Welcome to AIC-ADE

AIC-ADE is your AI-powered development environment. It helps you build software faster by providing intelligent assistance throughout the development lifecycle.

## First Launch

### 1. Create Your Profile
On first launch, you'll be asked to enter a display name. This is stored locally and identifies you in the application.

### 2. Configure an AI Provider
Before you can chat with AI, you need to configure a provider:

1. Go to **Settings → Providers**
2. Click **Add Provider**
3. Enter your provider details:
   - **Name**: A friendly name (e.g., "OpenAI")
   - **Endpoint**: API URL (e.g., `https://api.openai.com`)
   - **API Key**: Your API key
4. Click **Test Connection** to verify
5. Click **Save**

### 3. Start Chatting
Once a provider is configured, you can start chatting:

1. Click **New Conversation** or use an existing one
2. Type your message in the chat input
3. Press Enter or click Send
4. The AI will respond with assistance

## Core Features

### Chat
- Ask questions about your code
- Request code generation
- Get explanations and documentation
- Debug issues

### Projects
- Organize work into projects
- Track progress and milestones
- Manage tasks and deadlines

### Timeline
- View project history
- Track decisions and changes
- Monitor progress

## Engineering Intelligence

AIC-ADE includes a powerful engineering intelligence pipeline:

### Discovery
When you describe what you want to build, the Discovery engine:
- Analyzes your requirements
- Identifies ambiguities
- Asks clarifying questions
- Creates an engineering brief

### Planning
The Planning engine:
- Reviews the engineering brief
- Makes technical decisions
- Assesses risks
- Creates an engineering plan

### Task Graph
The Task Graph engine:
- Decomposes the plan into tasks
- Identifies dependencies
- Determines execution order
- Optimizes for parallelism

### Execution
The Dispatcher:
- Assigns tasks to workers
- Monitors execution
- Handles failures
- Collects results

### Verification
The Verification engine:
- Validates output meets requirements
- Checks quality standards
- Identifies issues
- Provides recommendations

## Tips & Tricks

### Effective Prompts
- Be specific about what you want
- Provide context about your project
- Mention constraints or requirements
- Ask for explanations when needed

### Managing Conversations
- Use folders to organize conversations
- Pin important conversations
- Archive completed work
- Use tags for easy searching

### Keyboard Shortcuts
- `Ctrl+N`: New conversation
- `Ctrl+K`: Quick search
- `Ctrl+Enter`: Send message
- `Ctrl+Shift+P`: Command palette

## Troubleshooting

### "No provider configured"
You need to configure an AI provider in Settings → Providers before chatting.

### Slow responses
- Check your internet connection
- Verify provider status in Settings
- Try a different provider or model

### Application won't start
- Ensure no other instance is running
- Check system requirements
- Review logs in the application data directory

## Getting Help

- **Documentation**: See the `docs/` directory
- **Issues**: Report bugs on GitHub
- **Community**: Join our Discord

## System Requirements

- **OS**: Windows 10+, macOS 10.15+, Ubuntu 20.04+
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 500MB free space
- **Network**: Internet for AI provider access

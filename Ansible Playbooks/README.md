# Ansible Homelab Automation
 
## What is Ansible?
 
**Ansible** is an open-source IT automation tool that allows you to automate provisioning, configuration management, and application deployment all without installing any agents on the systems you're managing.
 
It works by connecting to your hosts over **SSH** (or WinRM for Windows) and pushing out small programs called **modules** that do the work, then removing them when finished. All of your automation logic lives in human-readable **YAML** files called **playbooks**.
 
## About This Repository
 
This repo holds all the Ansible playbooks and roles I'll be creating to automate my homelab. The long-term goal is a single comprehensive playbook that fully provisions and configures the entire lab from scratch with no manual setup required. I'm building toward that by starting small, writing focused playbooks for individual tasks, and gradually rolling them into that master playbook over time.
 

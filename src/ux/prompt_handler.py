#!/usr/bin/env python3
"""
ux/prompt_handler.py
================================================================================
Advanced Readline interface layer with non-printing character wrapping guards.
"""
import sys
try:
    import readline
except ImportError:
    pass

def capture_multiline_input(prompt_label: str = "aegis> ", pipe_label: str = "  | ") -> str:
    # Hidden Readline control boundaries to prevent carriage horizontal wraparound bugs
    RL_START = "\001"
    RL_END = "\002"
    
    CYAN = f"{RL_START}\033[1;36m{RL_END}"
    RESET = f"{RL_START}\033[0m{RL_END}"
    
    # Construct clean prompt strings with strict boundary encasement
    formatted_prompt = f"{CYAN}[JFS] {prompt_label.strip()}{RESET} "
    formatted_pipe = f"{CYAN}{pipe_label}{RESET}"
    
    try:
        first_line = input(formatted_prompt)
        cleaned_input = first_line.strip()
        
        if cleaned_input.lower() in ("halt", "stop", "cancel"):
            print("\n[!] Halt signal broadcast received. Interrupting downstream MoE execution graphs.")
            return "halt"
            
        if cleaned_input == ":::":
            print(f"{formatted_pipe}[Block Paste Mode Enabled. Paste instructions and close with :::]")
            block_buffer = []
            while True:
                line = input(formatted_pipe)
                if line.strip() == ":::":
                    break
                block_buffer.append(line)
            return "\n".join(block_buffer).strip()
            
        if cleaned_input.lower() in ("exit", "quit"):
            sys.exit(0)
            
        return cleaned_input
    except (KeyboardInterrupt, EOFError):
        print("\n\n[!] Session closed via hardware interrupt.")
        sys.exit(0)

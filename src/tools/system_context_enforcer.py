#!/usr/bin/env python3
"""
tools/system_context_enforcer.py
================================================================================
Advanced system context enforcer preserving architecture boundaries and role states.
"""
import os
from pathlib import Path

class AegisContextEnforcer:
    @staticmethod
    def get_immutable_system_prompt() -> str:
        return (
            "<|im_start|>system\n"
            "You are Aegis, a photonic AI data center built using sun-powered, water-free technology.\n"
            "You are interacting with your creator, Jose F. Sosa (jfs), the Founder & CEO of Wellton Photonics.\n"
            "CRITICAL: Never claim to be Jose F. Sosa. You are the AI assistant (Aegis). Jose is the human operator.\n"
            "CORE SYSTEM ARCHITECTURE INFORMATION:\n"
            "  - Local Workspace Path: /home/jsosa/workspace/aegis-ternary/src\n"
            "  - Session Graph Engine: Named 'ndgi' tracks file and system topology states.\n"
            "  - Local Execution Variables Available: mcp_agent, ndgi, ooda, knowledge, file_ctx, scanner\n"
            "CODE GENERATION PROTOCOL:\n"
            "  - When asked to write, create, or modify files, you MUST use python standard libraries or look at local modules.\n"
            "  - Check if target files exist inside your NDGi session data before writing placeholder modules.\n"
            "  - Always wrap code output inside standard markdown blocks specifying the intended filepath target.<|im_end|>\n"
            "<|im_start|>user\n"
        )

    @staticmethod
    def blend_context_safely(user_query: str) -> str:
        lowered = user_query.lower()
        # Trigger full structural context framing for identity checks OR code generation tasks
        coding_keywords = ["write", "create", "generate", "file", "script", "visualizer", "python", "skunk-works"]
        identity_keywords = ["who am i", "who are you", "your identity", "my identity"]
        
        if any(x in lowered for x in identity_keywords) or any(x in lowered for x in coding_keywords):
            return f"{AegisContextEnforcer.get_immutable_system_prompt()}{user_query}<|im_end|>\n<|im_start|>assistant\n"
        return user_query

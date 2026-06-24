#!/usr/bin/env python3
"""
OODA Validation Wrapper - Validates BitNet+NDGi+MySQL code through consensus
Usage: python3 validate_and_commit.py <script_path>
"""

import sys
import json
from pathlib import Path
from ndgi_coding_agent import ODOACodingAgent, TritState, ODOAPhase

def read_code(script_path: str) -> str:
    """Read the code file to validate"""
    try:
        with open(script_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print(f"✗ File not found: {script_path}")
        return None

def validate_bitnet_mysql_code(code: str) -> tuple[TritState, list]:
    """
    Validate BitNet+NDGi+MySQL code against architectural rules
    Returns: (TritState, list of validation results)
    """
    rules = {
        "imports_present": "import torch" in code or "import mysql" in code,
        "error_handling": "try:" in code and "except" in code,
        "logging_setup": "logger" in code or "logging" in code,
        "database_schema": "CREATE TABLE" in code,
        "pstla_filter": "trust_state != 'POS'" in code or "PSTLA" in code,
        "ooda_phases": ("OBSERVE" in code or "[O]" in code) and ("ACT" in code or "[A]" in code),
        "documentation": '"""' in code or "'''" in code,
        "mysql_connection": "mysql.connector" in code,
    }
    
    passed = 0
    failed = []
    
    for rule_name, passed_check in rules.items():
        if passed_check:
            passed += 1
        else:
            failed.append(rule_name)
    
    # T-AND consensus: all must pass for TRIT_POS
    if passed == len(rules):
        return TritState.POS, failed
    elif passed > len(rules) * 0.5:
        return TritState.ZERO, failed  # Partial agreement
    else:
        return TritState.NEG, failed   # Contradiction

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_and_commit.py <script_path>")
        print("\nExample:")
        print("  python3 validate_and_commit.py bitnet_ndgi_mysql.py")
        return False
    
    script_path = sys.argv[1]
    
    # Initialize agent
    agent = ODOACodingAgent(project_root="~/BitNet")
    
    print("\n" + "="*70)
    print("OODA VALIDATION - BitNet + NDGi + MySQL Integration")
    print("="*70 + "\n")
    
    # OBSERVE: Check prior knowledge
    agent.log_entry(ODOAPhase.OBSERVE, "Checking NDGi for prior knowledge on BitNet+MySQL...")
    
    prior_bitnet = agent.ndgi.read("bitnet:setup")
    prior_cuda = agent.ndgi.read("system:cuda_status")
    prior_db = agent.ndgi.read("database:mysql_schema")
    
    print(f"\nPrior Knowledge:")
    print(f"  ✓ BitNet: {prior_bitnet.value[:60] if prior_bitnet else 'Not found'}...")
    print(f"  ✓ CUDA: {prior_cuda.value[:60] if prior_cuda else 'Not found'}...")
    print(f"  {'✓' if prior_db else '✗'} Database Schema: {'Known' if prior_db else 'New territory'}")
    
    # ORIENT: Identify expertise needed
    agent.log_entry(ODOAPhase.ORIENT, 
                   "Task requires: BitNet inference expert + Database schema expert + NDGi validator")
    print(f"\nExpertise routing:")
    print(f"  → code:bitnet_expert")
    print(f"  → code:database_expert")
    print(f"  → architecture:ndgi_validator")
    
    # DECIDE: Read and validate code
    print(f"\n[D] DECIDE: Validating {script_path}...")
    code = read_code(script_path)
    
    if not code:
        return False
    
    trust, failed_rules = validate_bitnet_mysql_code(code)
    
    print(f"\nValidation Results:")
    if trust == TritState.POS:
        print(f"  ✓ CONSENSUS: TRIT_POS (+1)")
        print(f"  ✓ All validation rules passed")
    elif trust == TritState.ZERO:
        print(f"  ⚠ CONSENSUS: TRIT_ZERO (0) - Partial agreement")
        print(f"  ✗ Failed rules: {', '.join(failed_rules)}")
    else:
        print(f"  ✗ CONSENSUS: TRIT_NEG (-1)")
        print(f"  ✗ Failed rules: {', '.join(failed_rules)}")
    
    agent.log_entry(ODOAPhase.DECIDE, 
                   f"Code validation complete. Trust: {trust.name}", trust)
    
    # ACT: PSTLA Filter
    print(f"\n[A] ACT: Applying PSTLA Filter...")
    
    if trust == TritState.POS:
        print(f"  ✓ TRIT_POS: Code approved for commit")
        
        # Write to NDGi
        agent.ndgi.write(
            f"code:bitnet_ndgi_mysql.py",
            f"BitNet + NDGi + MySQL integration - validated through T-AND consensus",
            TritState.POS
        )
        
        # Store validation record
        agent.ndgi.write(
            f"validation:bitnet_ndgi_mysql.py:{agent.session_id}",
            json.dumps({
                "script": script_path,
                "trust": "TRIT_POS",
                "rules_passed": 8,
                "timestamp": agent.session_id
            }),
            TritState.POS
        )
        
        print(f"  ✓ NDGi: Code metadata stored (TRIT_POS)")
        print(f"  → Ready to integrate into BitNet pipeline")
        
        result = True
        
    elif trust == TritState.ZERO:
        print(f"  ⚠ TRIT_ZERO: Code held for human review")
        print(f"  → Missing validation: {', '.join(failed_rules)}")
        print(f"  → Add these rules to script, then re-run validator")
        
        result = False
        
    else:  # TRIT_NEG
        print(f"  ✗ TRIT_NEG: Code rejected")
        print(f"  → Critical rules failed: {', '.join(failed_rules)}")
        
        # Log to lessons.md
        lessons_path = Path("~/BitNet/docs/lessons.md").expanduser()
        with open(lessons_path, 'a') as f:
            f.write(f"\n### {agent.session_id}\n")
            f.write(f"**Rejected**: {script_path}\n")
            f.write(f"**Failed Rules**: {', '.join(failed_rules)}\n")
            f.write(f"**Action**: Fix these issues and re-validate\n\n")
        
        print(f"  ✓ Recorded in: docs/lessons.md")
        
        result = False
    
    # Save session
    agent.save_session()
    
    print(f"\n" + "="*70)
    print(f"Session logged: .ooda/session_{agent.session_id}.md")
    print(f"="*70 + "\n")
    
    return result

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

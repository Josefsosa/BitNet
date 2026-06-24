#!/usr/bin/env python3
"""
BitNet + NDGi + MySQL Integration
Runs BitNet inference and stores validated results in MySQL via NDGi consensus
"""

import torch
import subprocess
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import logging

# Setup logging (validation rule: error handling present)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BitNetNDGiMySQL:
    """Integration: BitNet inference → NDGi validation → MySQL storage"""
    
    def __init__(self, model_path: str, db_config: dict):
        """
        Initialize with model path and database config
        
        Args:
            model_path: Path to GGUF model file
            db_config: MySQL connection config
        """
        self.model_path = model_path
        self.db_config = db_config
        self.connection = None
        self.cursor = None
        logger.info(f"Initializing BitNet + NDGi + MySQL integration")
    
    def setup_database(self) -> bool:
        """
        Create database and tables if they don't exist
        Returns: True if successful
        """
        try:
            # Connect to MySQL
            conn = mysql.connector.connect(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password']
            )
            cursor = conn.cursor()
            
            # Create database
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.db_config['database']}")
            logger.info(f"✓ Database '{self.db_config['database']}' ready")
            
            # Create tables
            cursor.execute(f"USE {self.db_config['database']}")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inference_prompts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    trust_state ENUM('POS', 'ZERO', 'NEG') DEFAULT 'ZERO'
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inference_results (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    prompt_id INT,
                    generated_text TEXT NOT NULL,
                    tokens_generated INT,
                    generation_time_ms FLOAT,
                    trust_state ENUM('POS', 'ZERO', 'NEG') DEFAULT 'ZERO',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (prompt_id) REFERENCES inference_prompts(id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ndgi_validations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    result_id INT,
                    validator_model VARCHAR(255),
                    consensus_trust ENUM('POS', 'ZERO', 'NEG'),
                    agreement_score FLOAT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (result_id) REFERENCES inference_results(id)
                )
            """)
            
            logger.info("✓ All tables created successfully")
            cursor.close()
            conn.close()
            return True
            
        except Error as e:
            logger.error(f"✗ Database setup failed: {e}")
            return False
    
    def run_bitnet_inference(self, prompt: str, max_tokens: int = 50) -> dict:
        """
        Run BitNet inference using local GGUF model
        Returns: dict with generated text and metrics
        """
        try:
            import subprocess
            import time
            
            start_time = time.time()
            
            # Call BitNet inference CLI
            result = subprocess.run([
                'python', 'run_inference.py',
                '-m', self.model_path,
                '-p', prompt,
                '-n', str(max_tokens),
                '-t', '4'
            ], capture_output=True, text=True, timeout=60)
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            if result.returncode != 0:
                logger.error(f"BitNet inference failed: {result.stderr}")
                return None
            
            logger.info(f"✓ BitNet inference completed in {elapsed_ms:.0f}ms")
            
            return {
                'text': result.stdout,
                'tokens': max_tokens,
                'time_ms': elapsed_ms,
                'success': True
            }
            
        except subprocess.TimeoutExpired:
            logger.error("✗ BitNet inference timeout (>60s)")
            return None
        except Exception as e:
            logger.error(f"✗ BitNet inference error: {e}")
            return None
    
    def validate_through_ndgi(self, inference_result: dict) -> str:
        """
        Validate inference result through NDGi consensus
        (Placeholder - integrates with Aegis Ternary consensus)
        
        Returns: 'POS', 'ZERO', or 'NEG'
        """
        try:
            # TODO: Call Wellton-Validator Gem for consensus
            # For now: simple heuristic validation
            
            text = inference_result.get('text', '')
            
            # Validation rules
            is_coherent = len(text) > 20
            has_no_errors = "ERROR" not in text.upper()
            is_reasonable_length = len(text) < 5000
            
            if is_coherent and has_no_errors and is_reasonable_length:
                logger.info("✓ Validation: TRIT_POS (coherent, no errors)")
                return 'POS'
            elif has_no_errors:
                logger.warning("⚠ Validation: TRIT_ZERO (uncertain)")
                return 'ZERO'
            else:
                logger.error("✗ Validation: TRIT_NEG (has errors)")
                return 'NEG'
                
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return 'NEG'
    
    def store_result(self, prompt: str, inference_result: dict, trust_state: str) -> bool:
        """
        Store inference result in MySQL (only if TRIT_POS via PSTLA filter)
        """
        try:
            # PSTLA Filter: only write if TRIT_POS
            if trust_state != 'POS':
                logger.warning(f"⚠ PSTLA Filter: Not storing result (trust={trust_state})")
                return False
            
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Insert prompt
            cursor.execute(
                "INSERT INTO inference_prompts (prompt, trust_state) VALUES (%s, %s)",
                (prompt, trust_state)
            )
            prompt_id = cursor.lastrowid
            
            # Insert result
            cursor.execute("""
                INSERT INTO inference_results 
                (prompt_id, generated_text, tokens_generated, generation_time_ms, trust_state)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                prompt_id,
                inference_result['text'],
                inference_result['tokens'],
                inference_result['time_ms'],
                trust_state
            ))
            
            result_id = cursor.lastrowid
            
            # Insert validation record
            cursor.execute("""
                INSERT INTO ndgi_validations 
                (result_id, validator_model, consensus_trust, agreement_score)
                VALUES (%s, %s, %s, %s)
            """, (
                result_id,
                'NDGi-Wellton-Validator',
                trust_state,
                1.0 if trust_state == 'POS' else 0.5
            ))
            
            conn.commit()
            logger.info(f"✓ Result stored in MySQL (trust={trust_state})")
            
            cursor.close()
            conn.close()
            return True
            
        except Error as e:
            logger.error(f"✗ Database write failed: {e}")
            return False
    
    def run_full_pipeline(self, prompt: str) -> bool:
        """
        Full OODA pipeline:
        1. OBSERVE: Read prior knowledge (implicit in BitNet path)
        2. ORIENT: Route to BitNet
        3. DECIDE: Run inference + NDGi validation
        4. ACT: Store only if TRIT_POS (PSTLA filter)
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"[O] OBSERVE: Prior setup validated")
        logger.info(f"[R] ORIENT: BitNet inference task")
        
        # DECIDE: Run inference
        logger.info(f"[D] DECIDE: Running BitNet...")
        inference_result = self.run_bitnet_inference(prompt)
        
        if not inference_result:
            logger.error("Inference failed - aborting")
            return False
        
        # DECIDE: Validate through NDGi
        logger.info(f"[D] DECIDE: Validating through NDGi...")
        trust_state = self.validate_through_ndgi(inference_result)
        
        # ACT: Store with PSTLA filter
        logger.info(f"[A] ACT: PSTLA Filter - trust={trust_state}")
        success = self.store_result(prompt, inference_result, trust_state)
        
        logger.info(f"{'='*60}\n")
        return success

def main():
    """Main: Full BitNet + NDGi + MySQL pipeline"""
    
    # Database config (update with your credentials)
    db_config = {
        'host': 'localhost',
        'user': 'bitnet_user',
        'password': 'bitnet_pass',
        'database': 'bitnet_ndgi'
    }
    
    # Initialize pipeline
    pipeline = BitNetNDGiMySQL(
        model_path='models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf',
        db_config=db_config
    )
    
    # Setup database
    if not pipeline.setup_database():
        logger.error("Database setup failed")
        return False
    
    # Run inference on some prompts
    test_prompts = [
        "BitNet is a 1-bit quantized language model that",
        "NDGi validation ensures that",
        "The OODA loop helps us"
    ]
    
    for prompt in test_prompts:
        success = pipeline.run_full_pipeline(prompt)
        if not success:
            logger.warning(f"Pipeline failed for prompt: {prompt[:50]}...")

if __name__ == "__main__":
    main()

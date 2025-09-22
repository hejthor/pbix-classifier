from typing import List, Dict, Optional, Tuple
import subprocess as _subprocess
import os as _os
import ollama
import sys as _sys
import re as _re

# Type aliases
StringList = List[str]
StringMap = Dict[str, str]

class OllamaClassifier:
    def __init__(self, model: str = "qwen2.5:1.5b"):
        self.model = model
        self.ollama_cmd = "ollama"
        self.use_cli = False
        
        # Ensure Ollama service is running
        self._ensure_ollama_running()
        # Ensure model is available
        self._ensure_model_available()
    
    def _run_command(self, cmd: str, check: bool = True) -> _subprocess.CompletedProcess:
        """Run a shell command and return the result."""
        try:
            return _subprocess.run(
                cmd,
                shell=True,
                check=check,
                text=True,
                capture_output=True
            )
        except _subprocess.CalledProcessError as e:
            print(f"Command failed with error: {e.stderr}", file=_sys.stderr)
            raise
    
    def _is_ollama_running(self) -> bool:
        """Check if Ollama service is running."""
        try:
            if self.use_cli:
                result = self._run_command(f"{self.ollama_cmd} list", check=False)
                return result.returncode == 0
            else:
                # Try to get model list using Python API
                models = ollama.list()
                return True
        except Exception:
            return False
    
    def _ensure_ollama_running(self):
        """Ensure Ollama service is running, start it if not."""
        if not self._is_ollama_running():
            print("Starting Ollama service...")
            try:
                # Start Ollama in the background
                _subprocess.Popen(
                    [self.ollama_cmd, "serve"],
                    stdout=_subprocess.PIPE,
                    stderr=_subprocess.PIPE,
                    creationflags=_subprocess.CREATE_NEW_CONSOLE
                )
                # Give it some time to start
                import time
                time.sleep(5)
            except Exception as e:
                print(f"Failed to start Ollama service: {e}", file=_sys.stderr)
                raise
    
    def _is_model_available(self) -> bool:
        """Check if the model is available locally."""
        try:
            if self.use_cli:
                result = self._run_command(f"{self.ollama_cmd} list", check=True)
                return self.model in result.stdout
            else:
                models = ollama.list()
                return any(model['name'] == self.model for model in models.get('models', []))
        except Exception as e:
            print(f"Error checking for model: {e}", file=_sys.stderr)
            return False
    
    def _ensure_model_available(self):
        """Ensure the model is available, pull it if not."""
        if not self._is_model_available():
            print(f"Model '{self.model}' not found. Downloading...")
            try:
                if self.use_cli:
                    self._run_command(f"{self.ollama_cmd} pull {self.model}")
                else:
                    ollama.pull(self.model)
                print(f"Successfully downloaded model '{self.model}'")
            except Exception as e:
                print(f"Failed to download model: {e}", file=_sys.stderr)
                raise
        
    def _normalize(self, text: str) -> str:
        """Normalize text by lowercasing and trimming."""
        return text.lower().strip()
    
    def _normalize_value(self, text: str) -> str:
        """Normalize value by lowercasing, trimming, and removing trailing punctuation."""
        text = self._normalize(text)
        return _re.sub(r'[^\w\s]|_$', '', text)
    
    def _load_categories(self, class_file: str) -> Tuple[StringList, StringList]:
        """Load and normalize categories from file."""
        orig_cats = []
        norm_cats = []
        
        with open(class_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Extract text after arrow if present
                if "→" in line:
                    line = line.split("→", 1)[1].strip()
                orig_cats.append(line)
                norm_cats.append(self._normalize(line))
                
        return orig_cats, norm_cats
    
    def _generate_prompt(self, value: str, categories: StringList, examples: str) -> str:
        """Generate the prompt for Ollama."""
        prompt = (
            "You are an expert in data classification. Your task is to classify the given value "
            "into one of the provided categories based on the context and meaning of the value.\n\n"
            f"Available categories (case-insensitive): {', '.join(categories)}\n\n"
        )
        
        if examples:
            prompt += "Here are some examples of values and their categories:\n"
            prompt += examples + "\n\n"
            
        prompt += (
            f"Input value to classify: {value}\n"
            "Please respond with ONLY the category name that best matches the input value, "
            "without any additional explanation or punctuation. If the value doesn't clearly match any "
            "category, respond with ''."
        )
        
        return prompt
        
    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama with the given prompt and return the response."""
        if not self.use_cli:
            try:
                response = ollama.generate(
                    model=self.model,
                    prompt=prompt,
                    options={
                        'temperature': 0.1,  # Lower temperature for more deterministic outputs
                        'num_predict': 100,  # Limit response length
                        'stop': ['\n', '.', ';']  # Stop at common sentence endings
                    }
                )
                return response['response'].strip()
            except Exception as e:
                print(f"Error calling Ollama: {e}", file=_sys.stderr)
                return ""
        else:
            try:
                cmd = [self.ollama_cmd, 'run', self.model, prompt]
                result = _subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=30,  # 30 second timeout
                    check=True
                )
                return result.stdout.strip()
            except _subprocess.CalledProcessError as e:
                print(f"Error calling Ollama: {e}", file=_sys.stderr)
                print(f"STDERR: {e.stderr}", file=_sys.stderr)
                return ""
            except _subprocess.TimeoutExpired:
                print("Ollama request timed out after 30 seconds", file=_sys.stderr)
                return ""
            
    def classify_value(self, value: str, categories: StringList) -> str:
        """Classify a single value using Ollama."""
        if not value.strip():
            return ""
            
        # Generate and send prompt
        prompt = self._generate_prompt(value, categories, "")
        response = self._call_ollama(prompt)
        
        # Normalize and validate response
        norm_response = self._normalize(response)
        for cat in categories:
            if self._normalize(cat) == norm_response:
                return cat
                
        # If we get here, the response didn't match any category
        return ""
        
    def process_files(self, categories: List[str], values: List[str], output_file: str) -> None:
        """Process values and save classifications as semicolon-separated CSV.
        
        Args:
            categories: List of category strings to classify into
            values: List of values to classify
            output_file: Path where the classified results will be saved
        """
        # Normalize categories
        orig_cats = categories
        norm_cats = [self._normalize(cat) for cat in categories]
        
        # Ensure output directory exists
        _os.makedirs(_os.path.dirname(output_file) or '.', exist_ok=True) 
        
        # Get unique values while preserving order
        unique_values = []
        seen = set()
        for value in values:
            if value not in seen:
                seen.add(value)
                unique_values.append(value)
        
        total_unique = len(unique_values)
        print(f"Found {len(values)} total values, {total_unique} unique")
        
        # Process unique values and store results
        results = {}
        for i, value in enumerate(unique_values, 1):
            # Print progress
            progress = (i / total_unique) * 100
            print(f"\rClassifying unique values: {i}/{total_unique} ({progress:.1f}%)", end='', flush=True)
            
            # Classify the value
            category = self.classify_value(value, orig_cats)
            results[value] = category
        
        # Write all unique results to the output file
        with open(output_file, 'w', encoding='utf-8') as out_f:
            # Write CSV header
            out_f.write("Data;Classification\n")
            
            # Write each unique value and its classification
            for value, category in results.items():
                # Escape any semicolons in the value or category by wrapping in quotes if needed
                safe_value = f'"{value}"' if ';' in value else value
                safe_category = f'"{category}"' if ';' in category else category
                out_f.write(f"{safe_value};{safe_category}\n")
        
        print(f"\nClassification complete! Saved {len(results)} unique classifications to {output_file}")

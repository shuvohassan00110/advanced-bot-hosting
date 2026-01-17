# -*- coding: utf-8 -*-
"""
Code validation and syntax checking
"""

import ast
import sys
import subprocess
from pathlib import Path
from typing import Tuple, List, Dict

class CodeValidator:
    """Validates Python and JavaScript code for syntax errors"""
    
    @staticmethod
    def validate_python(file_path: Path) -> Tuple[bool, str, List[Dict]]:
        """
        Validate Python file syntax
        
        Returns:
            (is_valid, message, errors_list)
        """
        try:
            code = file_path.read_text(encoding='utf-8', errors='replace')
            
            # Try to parse with ast
            try:
                ast.parse(code)
                return True, "✅ No syntax errors found!", []
            
            except SyntaxError as e:
                error_info = {
                    'line': e.lineno,
                    'offset': e.offset,
                    'text': e.text.strip() if e.text else '',
                    'msg': e.msg
                }
                
                error_msg = (
                    f"❌ <b>Syntax Error Found!</b>\n\n"
                    f"📍 <b>Line {e.lineno}</b>\n"
                    f"📝 Code: <code>{e.text.strip() if e.text else 'N/A'}</code>\n"
                    f"⚠️ Error: <code>{e.msg}</code>\n\n"
                    f"💡 <i>Fix this error before running your bot.</i>"
                )
                
                return False, error_msg, [error_info]
                
        except Exception as e:
            return False, f"❌ Validation error: {str(e)}", []
    
    @staticmethod
    def validate_javascript(file_path: Path) -> Tuple[bool, str, List[Dict]]:
        """
        Validate JavaScript file syntax using Node.js
        
        Returns:
            (is_valid, message, errors_list)
        """
        try:
            # Try to check syntax using node
            result = subprocess.run(
                ['node', '--check', str(file_path)],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return True, "✅ No syntax errors found!", []
            else:
                error_msg = (
                    f"❌ <b>Syntax Error Found!</b>\n\n"
                    f"<code>{result.stderr}</code>\n\n"
                    f"💡 <i>Fix this error before running your bot.</i>"
                )
                return False, error_msg, []
                
        except FileNotFoundError:
            return True, "⚠️ Node.js not found - syntax check skipped", []
        except Exception as e:
            return False, f"❌ Validation error: {str(e)}", []
    
    @staticmethod
    def check_imports(file_path: Path) -> Tuple[List[str], List[str]]:
        """
        Extract imports from Python file
        
        Returns:
            (stdlib_imports, external_imports)
        """
        stdlib_modules = set(sys.stdlib_module_names)
        
        try:
            code = file_path.read_text(encoding='utf-8', errors='replace')
            tree = ast.parse(code)
            
            stdlib_imports = []
            external_imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split('.')[0]
                        if module in stdlib_modules:
                            stdlib_imports.append(module)
                        else:
                            external_imports.append(module)
                            
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module = node.module.split('.')[0]
                        if module in stdlib_modules:
                            stdlib_imports.append(module)
                        else:
                            external_imports.append(module)
            
            return list(set(stdlib_imports)), list(set(external_imports))
            
        except Exception:
            return [], []
    
    @staticmethod
    def suggest_requirements(external_imports: List[str]) -> str:
        """Generate requirements.txt suggestion based on imports"""
        
        # Common package name mappings
        package_mapping = {
            'aiogram': 'aiogram>=3.4.1',
            'telebot': 'pyTelegramBotAPI>=4.14.0',
            'telegram': 'python-telegram-bot>=20.0',
            'flask': 'flask>=3.0.0',
            'fastapi': 'fastapi>=0.110.0',
            'django': 'django>=5.0.0',
            'requests': 'requests>=2.31.0',
            'aiohttp': 'aiohttp>=3.9.0',
            'bs4': 'beautifulsoup4>=4.12.0',
            'selenium': 'selenium>=4.15.0',
            'pandas': 'pandas>=2.1.0',
            'numpy': 'numpy>=1.26.0',
            'PIL': 'Pillow>=10.1.0',
            'cv2': 'opencv-python>=4.8.0',
        }
        
        requirements = []
        for imp in external_imports:
            if imp in package_mapping:
                requirements.append(package_mapping[imp])
            else:
                requirements.append(imp)
        
        return '\n'.join(sorted(requirements))

def validate_file_on_upload(file_path: Path, file_type: str) -> Tuple[bool, str]:
    """
    Validate uploaded file
    
    Args:
        file_path: Path to file
        file_type: File type (py, js, etc)
    
    Returns:
        (is_valid, message)
    """
    validator = CodeValidator()
    
    if file_type == 'py':
        is_valid, message, errors = validator.validate_python(file_path)
        
        # Also check imports and suggest requirements
        if is_valid:
            stdlib, external = validator.check_imports(file_path)
            if external:
                suggestions = validator.suggest_requirements(external)
                message += (
                    f"\n\n📦 <b>Detected External Packages:</b>\n"
                    f"<code>{', '.join(external)}</code>\n\n"
                    f"💡 Suggested requirements.txt:\n"
                    f"<pre>{suggestions}</pre>"
                )
        
        return is_valid, message
    
    elif file_type == 'js':
        return validator.validate_javascript(file_path)
    
    else:
        return True, "✅ File uploaded successfully"
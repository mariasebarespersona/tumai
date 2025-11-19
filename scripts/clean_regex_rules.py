#!/usr/bin/env python3
"""
Clean all _wants_* regex rules from app.py.

This script removes:
1. All _wants_* function definitions
2. All if _wants_*() checks that bypass the router
"""

import re

def clean_app_py():
    with open("app.py", "r") as f:
        content = f.read()
    
    lines = content.split("\n")
    
    # Track which lines to remove
    remove_lines = set()
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Remove _wants_* function definitions (including their body)
        if line.startswith("def _wants_"):
            # Find the end of this function (next def or class at same indentation level)
            start_i = i
            i += 1
            while i < len(lines):
                next_line = lines[i]
                # Stop at next function/class definition at root level, or empty line followed by def/class
                if (next_line.startswith("def ") or next_line.startswith("class ") or 
                    (next_line.strip() == "" and i+1 < len(lines) and 
                     (lines[i+1].startswith("def ") or lines[i+1].startswith("class ")))):
                    break
                i += 1
            
            # Mark all lines in this function for removal
            for j in range(start_i, i):
                remove_lines.add(j)
            
            print(f"Removing function at lines {start_i+1}-{i} ({lines[start_i][:50]}...)")
            continue
        
        i += 1
    
    # Build new content without removed lines
    new_lines = [line for i, line in enumerate(lines) if i not in remove_lines]
    new_content = "\n".join(new_lines)
    
    # Now remove if _wants_*() blocks
    # This is trickier because we need to handle nested blocks
    # For now, let's just report them
    pattern = r"if _wants_\w+\("
    matches = list(re.finditer(pattern, new_content))
    
    if matches:
        print(f"\n⚠️  Found {len(matches)} 'if _wants_*()' checks that need manual removal:")
        for match in matches:
            # Find line number
            line_num = new_content[:match.start()].count("\n") + 1
            context_start = max(0, match.start() - 50)
            context_end = min(len(new_content), match.end() + 50)
            context = new_content[context_start:context_end].replace("\n", " ")
            print(f"  Line ~{line_num}: {context}")
    
    # Write back
    with open("app.py", "w") as f:
        f.write(new_content)
    
    print(f"\n✅ Removed {len(remove_lines)} lines ({len([l for l in lines if l.startswith('def _wants_')])} functions)")
    print(f"⚠️  Please manually remove the 'if _wants_*()' checks reported above")

if __name__ == "__main__":
    clean_app_py()


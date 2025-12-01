import os
from pypdf import PdfReader

def read_pdf(file_path):
    print(f"--- Reading {file_path} ---")
    try:
        reader = PdfReader(file_path)
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except:
                print("Could not decrypt.")
                return

        full_text = ""
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                full_text += f"\n--- Page {i+1} ---\n{text}"
        
        # Print ALL text
        print(full_text)
            
    except Exception as e:
        print(f"Error reading PDF: {e}")

if __name__ == "__main__":
    docs_dir = "docs"
    files = [
        "DOC-20250819-WA0096..pdf" 
    ]
    
    for f in files:
        path = os.path.join(docs_dir, f)
        if os.path.exists(path):
            read_pdf(path)

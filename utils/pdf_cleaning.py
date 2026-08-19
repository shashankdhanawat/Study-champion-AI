import re
def clean_text(text):
  text = re.sub(r'\s+', ' ', text)  # Replace multiple whitespace with a single space
  text = re.sub(r'\n+', '\n', text)  # Replace multiple newlines with a single newline
 
  text = text.strip()  # Remove leading and trailing whitespace
  return text  

    
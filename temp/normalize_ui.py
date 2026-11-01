"""Script to normalize typography floor and contrast in app.js and index.html."""
import re
from pathlib import Path

app_js_path = Path("ui/static/app.js")
content = app_js_path.read_text(encoding="utf-8")

# Replace text-[10px] and text-[11px] with text-xs
new_content = content.replace("text-[10px]", "text-xs").replace("text-[11px]", "text-xs")

# Replace text-slate-400 on badge/metadata with text-slate-500
new_content = new_content.replace("text-slate-400 uppercase", "text-slate-500 uppercase")
new_content = new_content.replace("text-slate-400 font-mono", "text-slate-500 font-mono")
new_content = new_content.replace("text-slate-400 font-normal", "text-slate-500 font-normal")

# Update cache buster in index.html as well
index_path = Path("ui/static/index.html")
index_content = index_path.read_text(encoding="utf-8")
index_content = index_content.replace("app.js?v=3.0.0", "app.js?v=3.1.0")

app_js_path.write_text(new_content, encoding="utf-8")
index_path.write_text(index_content, encoding="utf-8")
print("Normalized typography and contrast in app.js and index.html.")


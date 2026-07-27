import sys

path = 'ui/src-tauri/src/lib.rs'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()
    
target = '''    let python_path = project_root.join(".venv/bin/python");
    
    // Start the Python embedded backend with stdin/stdout/stderr pipes
    let mut cmd = Command::new(if python_path.exists() { python_path.to_str().unwrap() } else { "python3" });'''

replacement = '''    let python_path_unix = project_root.join(".venv/bin/python");
    let python_path_win = project_root.join(".venv/Scripts/python.exe");
    
    // Use absolute path for Windows to avoid Microsoft Store alias issues
    let python_cmd = if python_path_win.exists() {
        python_path_win.to_str().unwrap()
    } else if python_path_unix.exists() {
        python_path_unix.to_str().unwrap()
    } else {
        if cfg!(windows) { "python" } else { "python3" }
    };
    
    println!("DEBUG: Found Windows Python path: {}", python_path_win.display());
    println!("DEBUG: Does it exist? {}", python_path_win.exists());
    println!("DEBUG: Executing Python command: {}", python_cmd);
    
    // Start the Python embedded backend with stdin/stdout/stderr pipes
    let mut cmd = Command::new(python_cmd);'''

if target not in content:
    print("Target not found in lib.rs!")
    sys.exit(1)

new_content = content.replace(target, replacement)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)
    
print("Successfully patched lib.rs")

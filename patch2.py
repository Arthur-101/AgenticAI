import sys

path = 'ui/src-tauri/src/lib.rs'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# We need to replace the project_root resolution logic.
target = '''    // Get the path to the Python embedded backend
    let script_path = std::path::Path::new("../../src/api/embedded_backend.py")
        .canonicalize()
        .map_err(|e| format!("Could not find embedded_backend.py: {}", e))?;
        
    let project_root = std::path::Path::new("../../")
        .canonicalize()
        .map_err(|e| format!("Could not find project root: {}", e))?;'''

replacement = '''    // Robustly find the project root by checking current dir and ancestors
    let mut current_dir = std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."));
    let mut project_root = None;
    
    // Search upwards up to 3 levels to find "src/api/embedded_backend.py"
    for _ in 0..4 {
        if current_dir.join("src/api/embedded_backend.py").exists() {
            project_root = Some(current_dir.clone());
            break;
        }
        if !current_dir.pop() {
            break;
        }
    }
    
    let project_root = project_root.ok_or_else(|| "Could not find project root containing src/api/embedded_backend.py".to_string())?;
    let script_path = project_root.join("src/api/embedded_backend.py");'''

if target not in content:
    print("Target not found in lib.rs!")
    sys.exit(1)

new_content = content.replace(target, replacement)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)
    
print("Successfully patched lib.rs with robust path resolution")

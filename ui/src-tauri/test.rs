fn main() {
    let script_path = std::path::Path::new("../../src/api/embedded_backend.py").canonicalize();
    println!("script_path = {:?}", script_path);
    let project_root = std::path::Path::new("../../").canonicalize();
    println!("project_root = {:?}", project_root);
    if let Ok(root) = project_root {
        let python_path = root.join(".venv/Scripts/python.exe");
        println!("python_path = {:?}", python_path);
        println!("exists? {}", python_path.exists());
    }
}

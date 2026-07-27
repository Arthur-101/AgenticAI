use std::process::Command;
fn main() {
    let python_path = "\\\\?\\E:\\Codes\\AgenticAI\\.venv\\Scripts\\python.exe";
    println!("Running: {}", python_path);
    let mut cmd = Command::new(python_path);
    cmd.arg("--version");
    match cmd.status() {
        Ok(s) => println!("Success: {}", s),
        Err(e) => println!("Error: {}", e),
    }
}

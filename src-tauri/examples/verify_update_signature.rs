use base64::{engine::general_purpose::STANDARD, Engine as _};
use minisign_verify::{PublicKey, Signature};
use std::path::Path;

fn decoded_text(value: &str, label: &str) -> Result<String, String> {
    let decoded = STANDARD
        .decode(value.trim())
        .map_err(|_| format!("{label} is not valid base64"))?;
    String::from_utf8(decoded).map_err(|_| format!("{label} is not valid UTF-8"))
}

fn verify_update_signature(
    archive: &[u8],
    signature_base64: &str,
    public_key_base64: &str,
) -> Result<(), String> {
    let public_key_text = decoded_text(public_key_base64, "public key")?;
    let signature_text = decoded_text(signature_base64, "signature")?;
    let public_key = PublicKey::decode(&public_key_text)
        .map_err(|error| format!("public key could not be decoded: {error}"))?;
    let signature = Signature::decode(&signature_text)
        .map_err(|error| format!("signature could not be decoded: {error}"))?;
    public_key
        .verify(archive, &signature, true)
        .map_err(|error| format!("updater signature verification failed: {error}"))
}

fn run() -> Result<(), String> {
    let mut args = std::env::args_os().skip(1);
    let archive_path = args.next().ok_or_else(|| {
        "usage: verify_update_signature <archive> <signature> <public-key>".to_string()
    })?;
    let signature_path = args.next().ok_or_else(|| {
        "usage: verify_update_signature <archive> <signature> <public-key>".to_string()
    })?;
    let public_key = args.next().ok_or_else(|| {
        "usage: verify_update_signature <archive> <signature> <public-key>".to_string()
    })?;
    if args.next().is_some() {
        return Err("verify_update_signature received unexpected arguments".to_string());
    }
    let archive = std::fs::read(Path::new(&archive_path))
        .map_err(|error| format!("updater archive could not be read: {error}"))?;
    let signature = std::fs::read_to_string(Path::new(&signature_path))
        .map_err(|error| format!("updater signature could not be read: {error}"))?;
    let public_key = public_key
        .into_string()
        .map_err(|_| "public key is not valid Unicode".to_string())?;
    verify_update_signature(&archive, &signature, &public_key)
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
    println!("Updater archive signature is valid.");
}

#[cfg(test)]
mod tests {
    use super::*;

    const PUBLIC_KEY: &str = "untrusted comment: minisign public key E7620F1842B4E81F\nRWQf6LRCGA9i53mlYecO4IzT51TGPpvWucNSCh1CBM0QTaLn73Y7GFO3";
    const SIGNATURE: &str = "untrusted comment: signature from minisign secret key\nRWQf6LRCGA9i59SLOFxz6NxvASXDJeRtuZykwQepbDEGt87ig1BNpWaVWuNrm73YiIiJbq71Wi+dP9eKL8OC351vwIasSSbXxwA=\ntrusted comment: timestamp:1555779966\tfile:test\nQtKMXWyYcwdpZAlPF7tE2ENJkRd1ujvKjlj1m9RtHTBnZPa5WKU5uWRs5GoP5M/VqE81QFuMKI5k/SfNQUaOAA==";

    #[test]
    fn accepts_matching_tauri_encoded_signature() {
        let public_key = STANDARD.encode(PUBLIC_KEY);
        let signature = STANDARD.encode(SIGNATURE);
        assert!(verify_update_signature(b"test", &signature, &public_key).is_ok());
    }

    #[test]
    fn rejects_modified_archive() {
        let public_key = STANDARD.encode(PUBLIC_KEY);
        let signature = STANDARD.encode(SIGNATURE);
        assert!(verify_update_signature(b"tampered", &signature, &public_key).is_err());
    }
}

use monocle::MonocleConfig;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

fn env_lock() -> &'static Mutex<()> {
    static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    LOCK.get_or_init(|| Mutex::new(()))
}

struct EnvGuard {
    _lock: std::sync::MutexGuard<'static, ()>,
    saved: Vec<(String, Option<String>)>,
}

impl EnvGuard {
    fn new(vars: &[&str]) -> Self {
        let lock = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let mut saved = Vec::new();
        for var in vars {
            saved.push((var.to_string(), env::var(var).ok()));
        }
        Self { _lock: lock, saved }
    }

    fn set_var(&mut self, key: &str, value: &str) {
        env::set_var(key, value);
    }
}

impl Drop for EnvGuard {
    fn drop(&mut self) {
        for (key, value) in self.saved.drain(..) {
            match value {
                Some(v) => env::set_var(key, v),
                None => env::remove_var(key),
            }
        }
    }
}

fn unique_temp_dir(prefix: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("time went backwards")
        .as_nanos();
    let pid = std::process::id();
    let path = env::temp_dir().join(format!("monocle_{prefix}_{pid}_{nanos}"));
    fs::create_dir_all(&path).expect("failed to create temp dir");
    path
}

#[test]
fn test_xdg_config_and_data_dirs() {
    let mut guard = EnvGuard::new(&["HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"]);

    let home = unique_temp_dir("home_xdg_config");
    let xdg_config = unique_temp_dir("xdg_config");
    let xdg_data = unique_temp_dir("xdg_data");

    guard.set_var("HOME", home.to_str().expect("home path"));
    guard.set_var("XDG_CONFIG_HOME", xdg_config.to_str().expect("xdg config"));
    guard.set_var("XDG_DATA_HOME", xdg_data.to_str().expect("xdg data"));

    let config_path = MonocleConfig::config_file_path();
    let expected_config = xdg_config.join("monocle").join("monocle.toml");
    assert_eq!(
        Path::new(&config_path),
        expected_config,
        "config path should use XDG_CONFIG_HOME"
    );

    let config = MonocleConfig::new(&None).expect("config load should succeed");
    let expected_data_dir = xdg_data.join("monocle");
    assert_eq!(
        Path::new(&config.data_dir),
        expected_data_dir,
        "data dir should use XDG_DATA_HOME"
    );
    assert!(
        expected_config.exists(),
        "config file should be created in XDG config dir"
    );
    assert!(
        !home.join(".monocle").join("monocle.toml").exists(),
        "legacy config path should not be used when XDG_CONFIG_HOME is set"
    );
}

#[test]
fn test_xdg_cache_dir_override() {
    let mut guard = EnvGuard::new(&["HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"]);

    let home = unique_temp_dir("home_xdg_cache");
    let xdg_data = unique_temp_dir("xdg_data_cache");
    let xdg_cache = unique_temp_dir("xdg_cache");

    guard.set_var("HOME", home.to_str().expect("home path"));
    guard.set_var("XDG_DATA_HOME", xdg_data.to_str().expect("xdg data"));
    guard.set_var("XDG_CACHE_HOME", xdg_cache.to_str().expect("xdg cache"));

    let config = MonocleConfig::new(&None).expect("config load should succeed");
    let expected_cache_dir = xdg_cache.join("monocle");
    assert_eq!(
        Path::new(&config.cache_dir()),
        expected_cache_dir,
        "cache dir should use XDG_CACHE_HOME"
    );

    let expected_data_dir = xdg_data.join("monocle");
    assert_eq!(
        Path::new(&config.data_dir),
        expected_data_dir,
        "data dir should still use XDG_DATA_HOME"
    );
}

#[test]
fn test_legacy_config_migration() {
    let mut guard = EnvGuard::new(&["HOME", "XDG_CONFIG_HOME"]);

    let home = unique_temp_dir("home_legacy");
    let xdg_config = unique_temp_dir("xdg_config_legacy");

    guard.set_var("HOME", home.to_str().expect("home path"));
    guard.set_var("XDG_CONFIG_HOME", xdg_config.to_str().expect("xdg config"));

    let legacy_dir = home.join(".monocle");
    fs::create_dir_all(&legacy_dir).expect("create legacy dir");

    let legacy_config_path = legacy_dir.join("monocle.toml");
    let legacy_contents = "data_dir = '/tmp/legacy'\n";
    fs::write(&legacy_config_path, legacy_contents).expect("write legacy config");

    let new_config_path = xdg_config.join("monocle").join("monocle.toml");
    assert!(
        !new_config_path.exists(),
        "new config path should start empty"
    );

    let config = MonocleConfig::new(&None).expect("config load should succeed");
    assert!(
        new_config_path.exists(),
        "new config path should be created from legacy config"
    );

    let migrated_contents = fs::read_to_string(&new_config_path)
        .expect("read migrated config");
    assert_eq!(
        migrated_contents, legacy_contents,
        "legacy config should be copied into new config path"
    );

    assert_eq!(
        Path::new(&config.data_dir),
        Path::new("/tmp/legacy"),
        "migrated config should drive data_dir"
    );
}

#[test]
fn compute_feature_excludes_boolean_kernels() {
    assert!(cfg!(feature = "compute"));
    assert!(
        !cfg!(feature = "compute_boolean"),
        "compute_boolean should not be enabled by compute feature"
    );
    assert!(
        !cfg!(feature = "compute_boolean_kleene"),
        "compute_boolean_kleene should not be enabled by compute feature"
    );
}

use arrow::array::{Array, BooleanArray, Int32Array};
use arrow::compute::boolean;
use arrow::scalar::BooleanScalar;

#[test]
fn and_or_preserve_nulls_with_all_true_or_false_slices() {
    let all_true = BooleanArray::from_slice(vec![true, true, true, true, true, true]);
    let all_false = BooleanArray::from_slice(vec![false, false, false, false, false, false]);

    let with_nulls = BooleanArray::from(vec![
        None,
        Some(true),
        Some(false),
        None,
        Some(true),
        Some(false),
        None,
        Some(true),
    ]);

    let with_nulls = with_nulls.sliced(1, 6);
    let with_nulls = with_nulls.as_any().downcast_ref::<BooleanArray>().unwrap();

    let all_true = all_true.sliced(0, 6);
    let all_true = all_true.as_any().downcast_ref::<BooleanArray>().unwrap();

    let all_false = all_false.sliced(0, 6);
    let all_false = all_false.as_any().downcast_ref::<BooleanArray>().unwrap();

    let and_result = boolean::and(with_nulls, all_true);
    assert_eq!(and_result, with_nulls.clone());

    let or_result = boolean::or(with_nulls, all_false);
    assert_eq!(or_result, with_nulls.clone());

    let and_all_false = boolean::and(with_nulls, all_false);
    let expected_false = BooleanArray::from(vec![
        None,
        Some(false),
        Some(false),
        None,
        Some(false),
        Some(false),
    ]);
    assert_eq!(and_all_false, expected_false);

    let or_all_true = boolean::or(with_nulls, all_true);
    let expected_true = BooleanArray::from(vec![
        None,
        Some(true),
        Some(true),
        None,
        Some(true),
        Some(true),
    ]);
    assert_eq!(or_all_true, expected_true);
}

#[test]
fn any_all_handle_sparse_validity_and_offsets() {
    let array = BooleanArray::from(vec![
        None,
        Some(false),
        None,
        Some(false),
        None,
        Some(true),
        Some(false),
        None,
    ]);

    let slice = array.sliced(1, 6);
    let slice = slice.as_any().downcast_ref::<BooleanArray>().unwrap();

    assert!(boolean::any(slice));
    assert!(!boolean::all(slice));

    let only_nulls = BooleanArray::from(vec![None, None, None, None, None, None]);
    assert!(!boolean::any(&only_nulls));
    assert!(boolean::all(&only_nulls));
}

#[test]
fn null_checks_match_scalar_ops_with_sliced_input() {
    let array = Int32Array::from(vec![
        Some(10),
        None,
        Some(20),
        None,
        Some(30),
        None,
        Some(40),
    ]);

    let sliced = array.sliced(1, 5);

    let is_null = boolean::is_null(&sliced);
    let is_not_null = boolean::is_not_null(&sliced);

    let expected_nulls = BooleanArray::from_slice(vec![true, false, true, false, true]);
    let expected_not_nulls = BooleanArray::from_slice(vec![false, true, false, true, false]);

    assert_eq!(is_null, expected_nulls);
    assert_eq!(is_not_null, expected_not_nulls);

    let scalar_true = BooleanScalar::new(Some(true));
    let scalar_false = BooleanScalar::new(Some(false));

    let and_true = boolean::and_scalar(&expected_nulls, &scalar_true);
    assert_eq!(and_true, expected_nulls.clone());

    let or_false = boolean::or_scalar(&expected_not_nulls, &scalar_false);
    assert_eq!(or_false, expected_not_nulls);
}

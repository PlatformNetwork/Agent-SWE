use polars_arrow::array::{Array, BooleanArray};
use polars_arrow::compute::boolean_kleene;
use polars_arrow::scalar::BooleanScalar;

#[test]
fn and_scalar_none_respects_kleene_false_short_circuit() {
    let array = BooleanArray::from(&[Some(true), Some(false), None, Some(true)]);
    let scalar = BooleanScalar::new(None);

    let result = boolean_kleene::and_scalar(&array, &scalar);

    let expected = BooleanArray::from(&[None, Some(false), None, None]);
    assert_eq!(result, expected);
}

#[test]
fn or_scalar_none_respects_kleene_true_short_circuit() {
    let array = BooleanArray::from(&[Some(true), Some(false), None, Some(false)]);
    let scalar = BooleanScalar::new(None);

    let result = boolean_kleene::or_scalar(&array, &scalar);

    let expected = BooleanArray::from(&[Some(true), None, None, None]);
    assert_eq!(result, expected);
}

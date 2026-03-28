@@ -19,6 +19,7 @@
     InferenceLogs,
 )
 from fme.core.generics.data import DataLoader, GriddedDataABC, InferenceDataABC
+from fme.core.generics.lr_tuning import LRTuningConfig
 from fme.core.generics.optimization import OptimizationABC
 from fme.core.generics.trainer import (
     AggregatorBuilderABC,
@@ -234,6 +235,7 @@ class Config:
     segment_epochs: int | None = None
     evaluate_before_training: bool = False
     save_best_inference_epoch_checkpoints: bool = False
+    lr_tuning: LRTuningConfig | None = None
 
     def __post_init__(self):
         start_epoch = 0 if self.evaluate_before_training else 1
@@ -340,6 +342,7 @@ def get_trainer(
     scheduler_config: SchedulerConfig | None = None,
     n_validation_batches: int = 5,
     save_checkpoint: bool = True,
+    lr_tuning: LRTuningConfig | None = None,
 ) -> tuple[TrainConfigProtocol, Trainer]:
     if checkpoint_dir is None:
         checkpoint_dir = os.path.join(tmp_path, "checkpoints")
@@ -415,6 +418,7 @@ def build_ema(modules: torch.nn.ModuleList) -> EMATracker:
         evaluate_before_training=evaluate_before_training,
         save_best_inference_epoch_checkpoints=save_best_inference_epoch_checkpoints,
         save_checkpoint=save_checkpoint,
+        lr_tuning=lr_tuning,
     )
     aggregator_builder = AggregatorBuilder(
         train_losses=train_losses,
@@ -1188,6 +1192,167 @@ def test_ema_state_preserved_after_resume(tmp_path: str):
         )
 
 
+def test_lr_tuning_disabled_by_default(tmp_path: str):
+    """When lr_tuning is None, training proceeds normally."""
+    with mock_wandb():
+        config, trainer = get_trainer(
+            tmp_path,
+            max_epochs=2,
+            lr_tuning=None,
+        )
+        initial_lr = trainer.optimization.learning_rate
+        trainer.train()
+        # LR should only change if the scheduler changes it, not LR tuning
+        assert trainer.optimization.learning_rate == initial_lr
+
+
+def test_lr_tuning_runs_and_keeps_lr(tmp_path: str):
+    """When the candidate doesn't win, the LR stays the same."""
+    max_epochs = 2
+    # epochs=Slice(), max_epochs=2:
+    # Epoch 0 tune: trial(0.7, 0.75)
+    #   threshold = 0.7 - 0.1*0.7 = 0.63; candidate 0.75 > 0.63 → baseline wins
+    # Epoch 0: train + validate(0.6)
+    # Epoch 1 tune: trial(0.5, 0.55)
+    #   threshold = 0.5 - 0.1*0.5 = 0.45; candidate 0.55 > 0.45 → baseline wins
+    # Epoch 1: train + validate(0.4)
+    validation_losses = np.array([0.7, 0.75, 0.6, 0.5, 0.55, 0.4])
+    with mock_wandb():
+        config, trainer = get_trainer(
+            tmp_path,
+            max_epochs=max_epochs,
+            validation_losses=validation_losses,
+            lr_tuning=LRTuningConfig(
+                epochs=Slice(),
+                lr_factor=0.5,
+                num_batches=2,
+                improvement_threshold=0.1,
+            ),
+        )
+        initial_lr = trainer.optimization.learning_rate
+        trainer.train()
+        assert trainer.optimization.learning_rate == initial_lr
+
+
+def test_lr_tuning_adopts_candidate_lr(tmp_path: str):
+    """When the candidate wins, the LR is updated."""
+    max_epochs = 2
+    # Epoch 0 tune: trial(0.9, 0.3)
+    #   threshold = 0.9 - 0.1*0.9 = 0.81; candidate 0.3 < 0.81 → candidate wins
+    # Epoch 0: train + validate(0.5)
+    # Epoch 1 tune: trial(0.45, 0.3)
+    #   threshold = 0.45 - 0.1*0.45 = 0.405; candidate 0.3 < 0.405 → candidate wins
+    # Epoch 1: train + validate(0.3)
+    validation_losses = np.array([0.9, 0.3, 0.5, 0.45, 0.3, 0.3])
+    with mock_wandb():
+        config, trainer = get_trainer(
+            tmp_path,
+            max_epochs=max_epochs,
+            validation_losses=validation_losses,
+            lr_tuning=LRTuningConfig(
+                epochs=Slice(),
+                lr_factor=0.5,
+                num_batches=2,
+                improvement_threshold=0.1,
+            ),
+        )
+        initial_lr = trainer.optimization.learning_rate
+        trainer.train()
+        # Candidate won at both epochs
+        assert trainer.optimization.learning_rate == initial_lr * 0.5 * 0.5
+
+
+def test_lr_tuning_respects_epochs_slice(tmp_path: str):
+    """LR tuning only runs on epochs matching the slice."""
+    max_epochs = 4
+    # epochs=Slice(step=2), so tuning runs at epoch 0 and 2
+    # Epoch 0 tune:
+    #   trial baseline: 0.7, candidate: 0.3
+    #   threshold = 0.7 - 0.1*0.7 = 0.63; candidate 0.3 < 0.63 → candidate wins
+    # Epoch 0 train + validate: 0.6
+    # Epoch 1: no tuning. train + validate: 0.5
+    # Epoch 2 tune:
+    #   trial baseline: 0.4, candidate: 0.1
+    #   threshold = 0.4 - 0.1*0.4 = 0.36; candidate 0.1 < 0.36 → candidate wins
+    # Epoch 2 train + validate: 0.3
+    # Epoch 3: no tuning. train + validate: 0.2
+    validation_losses = np.array(
+        [
+            0.7,
+            0.3,  # trial at epoch 0 (baseline, candidate)
+            0.6,  # epoch 0 validate
+            0.5,  # epoch 1 validate
+            0.4,
+            0.1,  # trial at epoch 2 (baseline, candidate)
+            0.3,  # epoch 2 validate
+            0.2,  # epoch 3 validate
+        ]
+    )
+    with mock_wandb():
+        config, trainer = get_trainer(
+            tmp_path,
+            max_epochs=max_epochs,
+            train_losses=np.zeros(max_epochs),
+            validation_losses=validation_losses,
+            inference_losses=np.zeros(max_epochs),
+            stepper_module_values=np.zeros(max_epochs),
+            lr_tuning=LRTuningConfig(
+                epochs=Slice(step=2),
+                lr_factor=0.5,
+                num_batches=2,
+                improvement_threshold=0.1,
+            ),
+        )
+        initial_lr = trainer.optimization.learning_rate
+        trainer.train()
+        # Tuning ran at epoch 0 and 2, candidate won both times
+        assert trainer.optimization.learning_rate == initial_lr * 0.5 * 0.5
+
+
+def test_lr_tuning_with_evaluate_before_training(tmp_path: str):
+    """When evaluate_before_training=True, training still proceeds normally
+    and LR tuning uses the trial's own baseline val loss for comparison."""
+    max_epochs = 2
+    # evaluate_before_training: val=0.9
+    # epoch 0 tune:
+    #   trial baseline: 0.8, candidate: 0.3
+    #   threshold = 0.8 - 0.1*0.8 = 0.72; candidate 0.3 < 0.72 → candidate wins
+    # epoch 0 train + validate: 0.5
+    # epoch 1 tune:
+    #   trial baseline: 0.4, candidate: 0.45
+    #   threshold = 0.4 - 0.1*0.4 = 0.36; candidate 0.45 > 0.36 → baseline wins
+    # epoch 1 train + validate: 0.3
+    validation_losses = np.array(
+        [
+            0.9,  # evaluate_before_training
+            0.8,
+            0.3,  # trial at epoch 0
+            0.5,  # epoch 0 validate
+            0.4,
+            0.45,  # trial at epoch 1 (baseline wins)
+            0.3,  # epoch 1 validate
+        ]
+    )
+    with mock_wandb():
+        config, trainer = get_trainer(
+            tmp_path,
+            max_epochs=max_epochs,
+            validation_losses=validation_losses,
+            inference_losses=np.zeros(max_epochs + 1),
+            evaluate_before_training=True,
+            lr_tuning=LRTuningConfig(
+                epochs=Slice(),
+                lr_factor=0.5,
+                num_batches=2,
+                improvement_threshold=0.1,
+            ),
+        )
+        initial_lr = trainer.optimization.learning_rate
+        trainer.train()
+        # Only epoch 0 candidate won
+        assert trainer.optimization.learning_rate == initial_lr * 0.5
+
+
 @pytest.mark.parametrize(
     "module_list,expected_num_parameters",
     [

import json

from argus.callbacks import MonitorCheckpoint, \
    EarlyStopping, LoggingToFile, ReduceLROnPlateau

from torch.utils.data import DataLoader

from src.stacking.datasets import get_out_of_folds_data, StackingDataset
from src.stacking.transforms import get_transforms
from src.stacking.argus_models import StackingModel
from src import config


STACKING_EXPERIMENT = "stacking_007_fcnet_16032"

EXPERIMENTS = [
    'auxiliary_001',
    'auxiliary_007',
    'auxiliary_014',
    'auxiliary_017',
    'small_cat_002',
    'corr_noisy_003',
    'corr_noisy_004'
]
RS_PARAMS = {"base_size": 256, "reduction_scale": 4, "p_dropout": 0.06303391930169855, "lr": 6.41972773090878e-05,
             "patience": 5, "factor": 0.6644578098312048, "batch_size": 32}
BATCH_SIZE = RS_PARAMS['batch_size']
DATASET_SIZE = 128 * 256
CORRECTIONS = True
if config.kernel:
    NUM_WORKERS = 2
else:
    NUM_WORKERS = 8
SAVE_DIR = config.experiments_dir / STACKING_EXPERIMENT
PARAMS = {
    'nn_module': ('FCNet', {
        'in_channels': len(config.classes) * len(EXPERIMENTS),
        'num_classes': len(config.classes),
        'base_size': RS_PARAMS['base_size'],
        'reduction_scale': RS_PARAMS['reduction_scale'],
        'p_dropout': RS_PARAMS['p_dropout']
    }),
    'loss': 'BCEWithLogitsLoss',
    'optimizer': ('Adam', {'lr': RS_PARAMS['lr']}),
    'device': 'cuda',
}


def train_fold(save_dir, train_folds, val_folds, folds_data):
    train_dataset = StackingDataset(folds_data, train_folds,
                                    get_transforms(True),
                                    DATASET_SIZE)
    val_dataset = StackingDataset(folds_data, val_folds,
                                  get_transforms(False))

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE,
                              shuffle=True, drop_last=True,
                              num_workers=NUM_WORKERS)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE * 2,
                            shuffle=False, num_workers=NUM_WORKERS)

    model = StackingModel(PARAMS)

    callbacks = [
        MonitorCheckpoint(save_dir, monitor='val_lwlrap', max_saves=1),
        ReduceLROnPlateau(monitor='val_lwlrap',
                          patience=RS_PARAMS['patience'],
                          factor=RS_PARAMS['factor'],
                          min_lr=1e-8),
        EarlyStopping(monitor='val_lwlrap', patience=30),
        LoggingToFile(save_dir / 'log.txt'),
    ]

    model.fit(train_loader,
              val_loader=val_loader,
              max_epochs=700,
              callbacks=callbacks,
              metrics=['multi_accuracy', 'lwlrap'])


if __name__ == "__main__":
    if not SAVE_DIR.exists():
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
    else:
        print(f"Folder {SAVE_DIR} already exists.")

    with open(SAVE_DIR / 'source.py', 'w') as outfile:
        outfile.write(open(__file__).read())

    print("Model params", PARAMS)
    with open(SAVE_DIR / 'params.json', 'w') as outfile:
        json.dump(PARAMS, outfile)

    if CORRECTIONS:
        with open(config.corrections_json_path) as file:
            corrections = json.load(file)
        print("Corrections:", corrections)
    else:
        corrections = None

    folds_data = get_out_of_folds_data(EXPERIMENTS, corrections)

    for fold in config.folds:
        val_folds = [fold]
        train_folds = list(set(config.folds) - set(val_folds))
        save_fold_dir = SAVE_DIR / f'fold_{fold}'
        print(f"Val folds: {val_folds}, Train folds: {train_folds}")
        print(f"Fold save dir {save_fold_dir}")
        train_fold(save_fold_dir, train_folds, val_folds, folds_data)

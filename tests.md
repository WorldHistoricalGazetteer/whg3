## WHG v3 Tests 
_as of 10 Jan 2024_

### tests/test_place_collections.py
#### 1. [CollectionTestCase(PlaceCollection)](tests/test_place_collections.py)
    
    - test_add_places (sets)
    - test_add_dataset_places (all of a dataset)
    - test_add_and_remove_dataset_places

### tests/test_collectiongroups.py
#### 2. [CollectionGroupTestCase](tests/test_collectiongroups.py)
    - test_only_group_leader_can_create_collection_group
    - test_add_user_to_collection_group
    - test_submit_collection_to_group
    - test_withdraw_collection_from_group

#### 3. [CollectionGroupScenarioTestCase](tests/test_collectiongroups.py)
    - test_submit_collection_to_group
      - check, uncheck 'reviewed' flag
      - check, uncheck 'nominated' flag
    - test_withdraw_collection_from_group

### tests/test_places.py
#### 4. [DatasetAndPlaceModelsTest](tests/test_places.py)
    - test_dataset
    - test_place

### tests/test_validation.py
#### 5. [DatasetCreateViewTest (validation: upload, insert)](tests/test_validation.py)
    - test_validate_delim
    - test_ds_insert_delim (fails on missing_field.tsv)
    - test_end_to_end (fails)

### tests/test_wdlocal.py
#### 6. [ReconWD](tests/test_wdlocal.py)
    - testReconWDlocal (fails)





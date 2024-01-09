### WHG v3 Tests 
_as of 9 Jan 2024_

#### 1. [CollectionTestCase(PlaceCollection)](tests/test_place_collections.py)
    
    - test_add_places (sets)
    - test_add_dataset_places (all of a dataset)
    - test_add_and_remove_dataset_places

#### 2. [CollectionGroupTestCase](tests/test_collectiongroups.py)
    - test_only_group_leader_can_create_collection_group
    - test_add_user_to_collection_group
    - test_submit_collection_to_group
    - test_withdraw_collection_from_group

#### 3. [DatasetAndPlaceModelsTest](tests/test_places.py)
    - test_dataset
    - test_place

#### 4. [DatasetCreateViewTest (validation: upload, insert)](tests/test_validation.py)
    - test_validate_delim
    - test_ds_insert_delim (fails on missing_field.tsv)
    - test_end_to_end (fails)

#### 5. [ReconWD](tests/test_wdlocal.py)
    - testReconWDlocal (fails)





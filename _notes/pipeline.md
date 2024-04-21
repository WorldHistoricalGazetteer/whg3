### dataset pipeline

#### create dataset
 - `/datasets/create` form > DatasetCreate()
   - sniff file type
   - validate form
   - if json:
     - validation.validate_lpf(tempfn, 'coll')
     - save dataset (ds_status = 'uploaded')
       - signal: send_new_dataset_email()
     - insert.ds_insert_json()
     - create DatasetFile, Log objects
   - if delimited:
     - create dataframe, df
     - validation.validate_delim(df)
     - save dataset (ds_status = 'uploaded')
       - signal: send_new_dataset_email()
     - insert.ds_insert_delim()
     - create DatasetFile, Log objects
   - return redirect to /datasets/{id}/status

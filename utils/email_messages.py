# email body content used with main.utils.new_emailer() throughout the project
"""
welcome, new_user: user.email_confirmed = True; name, id
new_dataset: new dataset created
dataset_published: public=True
dataset_unpublished: public=False
dataset_indexed: ds_status='indexed'
contact_form, contact_reply: contact form submitted
align_success: reconciliation task completed (wdlocal or idx)
wikidata_recon_complete: ds_status='wd-complete'
# failed_upload: upload failed
recon_failed: reconciliation task FAILURE (wdlocal or idx)
align_idx: alignment task completed (idx)
align_wdlocal: alignment task completed (wdlocal)
maintenance: TODO
"""
EMAIL_MESSAGES = {
  'welcome': (
    'Greetings {greeting_name}! \n\n'
    'Thank you for registering for the World Historical Gazetteer (WHG). You can visit '
    '<a href="https://whgazetteer.org/tutorials/guide/">the WHG site guide</a> '
    'to learn more about services and features the platform provides.\n\n'
    'WHG is gathering contributions of place data—large and small, and for all regions and historical periods.'
    'WHG provides services for geocoding place names, linking records for "closely matched" places, '
    'and on request, publishing contributed datasets and user-created collections. '
    'WHG is an excellent resource for teachers and students. Teachers can use its place information '
    'to develop lessons and to make custom maps for presentation in lectures. \n\n'
    'The "Place Collection" feature enables building and publishing sets of user-annotated place records, '
    'accompanied by an explanatory essay, image, and links to external resources. '
    'The WHG "union index" of place attestations drawn from multiple contributed datasets will over time '
    'increasingly link the disparate research of contributors on the dimension of place. '
    'Furthermore, by bringing together all the known references for a place without privileging '
    'any particular one, it decenters colonial name making.\n\n'
    'We are accepting dataset and place collection contributions, which can be published on the site. '
    'If you would like to set up a consultation to discuss these in more detail, just reply to this message\n\n'
    'regards,\nThe WHG project team'
  ),
  'new_user': (
    'Hello there,\n\n'
    'So you know...{name} ({username}, id {id}) just registered on the site.\n\n'
    'regards,\nThe WHG auto emailer bot'
  ),
  'contact_form': (
    'Hello there,\n\n'
    '{name} ({username}; {user_email}), on the subject of {user_subject} says: \n\n'
    '{user_message}\n\n'
    'regards,\nThe WHG auto emailer bot'
  ),
  'contact_reply': (
    'Hello {greeting_name},\n\n'
    'We received your message concerning "{user_subject}" and will respond soon.\n\n'
    'regards,\nThe WHG project team'
  ),
  'new_dataset': (
    'So you know...the user {name} ({username}) has created a new dataset, '
    '{dataset_title} ({dataset_label}, {dataset_id}).\n\n'
    'regards,\nThe WHG auto emailer bot'
  ),
  'dataset_published': (
    'Dear {greeting_name},\n\n'
    'Thank you for publishing your dataset, {dataset_title} ({dataset_label}, {dataset_id}).\n'
    'It is now publicly viewable, and its records accessible in search and our API .\n\n'
    'regards,\nThe WHG project team'
  ),
  'dataset_unpublished': (
    'Dear {greeting_name},\n\n'
    'Your previously published dataset, {dataset_title} ({dataset_label}, {dataset_id}), '
    'has been made private again, and its records are no longer accessible in search and our API .\n\n'
    'If you have any questions, please contact our editor at {reply_to}\n\n'
    'regards,\nThe WHG project team'
  ),
  'dataset_indexed': (
    'Dear {greeting_name},\n\n'
    'Thank you for indexing your dataset, {dataset_title} ({dataset_label}, {dataset_id}).\n\n'
    'All of its records were already public; now many are linked with those for closely '
    'matched places coming from other projects.\n\n'
    'regards,\nThe WHG project team'
  ),
  'wikidata_review_complete': (
    'Dear {greeting_name},\n\n'
    're: {dataset_title} ({dataset_label}, {dataset_id})\n\n'
    'Thank you for reconciling your dataset to Wikidata.\n'
    'If you would like it to be published, please ensure its metadata is complete, then request a review '
    'by WHG editorial staff, in reply to this message.\n\n'
    'regards,\nThe WHG project team'
  ),
  'failed_insert': (
    'Dear {greeting_name},\n\n'
    'We see that your upload of {filename} failed upon insert to our database\n\n'
    'We are look into why and will get back to you within a day.\n\n'
    'regards,\nThe WHG project team'
  ),
  'recon_task_success': (
    'Dear {greeting_name},\n\n'
    'Your {taskname} reconciliation task for the {dstitle} dataset ({dslabel}) has completed.'
    '{counthit} records got a total of {totalhits} hits.\n'
    'View results on the "Linking" tab of your dataset page (you may have to refresh it).\n\n'
    'regards,\nThe WHG project team'
  ),
  'recon_task_failed': (
    'Dear {greeting_name},\n\n'
    'Your {taskname} reconciliation task for the {dstitle} dataset ({dslabel}) failed to complete.'
    'We are looking into why and will get back to you within a day.\n'
    'apologies and regards,\nThe WHG project team'
  ),
  'recon_task_test': (
    'Greetings {greeting_name}! Your TEST index alignment task for the {dstitle} dataset ({dslabel}) has completed.'
    '{counthit} records got a total of {totalhits} hits.\n'
    'This only previews potential results; no records were written to the index.\n'
    'View results on the "Linking" tab of your dataset page (you may have to refresh it).\n\n'
    'regards,\nThe WHG project team'
  ),
  "volunteer_offer_user": (
    'Hello {volunteer_greeting},\n\n'
    'Thank you for volunteering to help with reconciliation review for the datawet "{dataset_title}"'
    ' on the World Historical Gazetteer platform.\n\n'
    'The dataset owner, {owner_greeting} has been notified and should be in touch soon to discuss how you can help.\n\n'
    "If you don't hear from them or have any questions, please contact us by replying to this email\n\n"
    'regards,\nThe WHG project team'
  ),
  "volunteer_offer_owner": (
    'Hello {owner_greeting},\n\n'
    'The World Historical Gazetteer user {volunteer_greeting} (volunteer_username) has offered to help with '
    'reconciliation review on your dataset, "{dataset_title}".\n'
    'You can respond to them at {volunteer_email} or by replying to this email. When mutually agreed, simply add '
    '{volunteer_username} as a colleborator and they will have the necessary access. \n\n'
    'We recommend volunteers be made aware of your approach to match decisions before proceeding.\n\n'
    'regards,\nThe WHG project team'
  ),
  'download_ready': (
    'Dear {greeting_name},\n\n'
    'Your requested download of "{title}" is ready.\n'
    'You will find it listed in the "Downloads" section of your dashboard.\n\n'
    'All data made public in WHG carries a CC-BY-4.0 NC license, so its re-use cannot '
    'have commercial purposes, and attribution is required in all cases. '
    'The README.txt in the .zip file provides more information.\n\n'
    'regards,\nThe WHG project team'
  ),
  # TODO: down for 'maintenance' or 'upgrade'
  'maintenance': (
    'Dear {name},\n\n'
    'Because you have logged in to WHG within the last month or so, we are letting you know that'
    'the World Historical Gazetteer site will be undergoing scheduled maintenance on {downdate}, during '
    'the following time window:\n'
    '  CEST: 15:00-19:00 \n'
    '  London: 14:00-19:00 \n'
    '  UTC: 07:00-10:00 \n'
    '  EDT (US): 09:00-13:00 \n'
    '  Tokyo: 22:00-02:00 Mon\n'
    '  Beijing: 21:00-01:00 Mon\n\n'
    'The site might be temporarily unavailable during this period.\n\n'
    'Thank you for your understanding.'
  ),
  # 'align_idx': (
  #   'Dear {greeting_name},\n\n'
  #   'Your WHG index alignment task for the {dstitle} dataset ({dslabel}) has completed. '
  #   '{counthit} records got a total of {totalhits} hits.\n'
  #   'View results on the "Linking" tab of your dataset page (you may have to refresh it).\n\n'
  #   'regards,\nThe WHG project team'
  # ),
  # 'align_wdlocal': (
  #   'Dear {greeting_name},\n\n'
  #   'Your Wikidata alignment task for the {dstitle} dataset ({dslabel}) has completed.'
  #   '{counthit} records got a total of {totalhits} hits.\n'
  #   'View results on the "Linking" tab of your dataset page (you may have to refresh it).\n\n'
  #   'regards,\nThe WHG project team, via new_emailer()'
  # ),
  # Add more email bodies as needed
}

# / = done; * = checked
# from_email = whg@pitt
# admins = [Karl, Ali]
# editor = [Ali]
# developer = [Karl]
# reply_to = editor or developer for fails

# /* welcome: "welcome to WHG -> new user
# /* new_user: "new registration" -> admins
# /* new_dataset: "thanks for uploading" ->  dataset owner, cc editor, bcc developer

# ***  TODO: validate & insert errors ***
# failed_upload: "we'll look into it" -> dataset owner, cc developer

# *** TODO: now in task_emailer() ***
# wikidata_recon_complete: "thanks for reconciling" -> dataset owner, cc editor
# wikidata_recon_failed: "we'll look into it" -> dataset owner, cc developer

# signal on dataset save after status
# /*dataset_published: "thanks for publishing" -> dataset owner, cc admins
# /*dataset_indexed: "thanks for indexing" -> dataset owner, cc admins


# /* contact_form: "user says: yada yada" -> admins, reply_to sender
# /* contact_reply: "thanks for contacting us" -> sender, cc editor

# (
# 		'Hello {name},\n\n'
# 		'Welcome to the World Historical Gazetteer!\n\n'
# 		'The WHG is a free, open-access resource for researcher, educators, '
# 		'and anyone studying or teaching about the past.\n'
# 		'We hope you will find it useful, and we welcome your contributions.\n\n'
# 		'If you have any questions, please contact our editor at {reply_to}\n\n'
# 		'regards,\nThe WHG project team'
# 	)

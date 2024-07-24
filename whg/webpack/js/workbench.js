// Purpose: workbench-specific js

import '../css/workbench.css';

$(document).ready(function() {
  $(".help-matches").click(function() {
    window.location.href = `/documentation/#${$(this).data('id').replace('wb_', '')}`;
  });
})
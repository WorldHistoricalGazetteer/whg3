// Purpose: workbench-specific js

import '../css/workbench.css';

$(document).ready(function() {
  let page
  $(".help-matches").click(function() {
      page = $(this).data('id')
      console.log('help:', page)
      $('.selector').dialog('open');
    })
  $(".selector").dialog({
      resizable: false,
      autoOpen: false,
      height: $(window).height() * 0.7,
      width: $(window).width() * 0.6,
      title: "WHG Workbench Pathways",
      modal: true,
      buttons: {'Close': function() {console.log('close dialog'); $(this).dialog('close');}},
      open: function(event, ui) {
      $('#helpme').load('/media/help/workbench/'+page+'.html')
  },
    show: {effect: "fade",duration: 400},
    hide: {effect: "fade",duration: 400}
  });
})
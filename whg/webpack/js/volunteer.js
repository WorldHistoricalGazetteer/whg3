$(document).ready(function() {
  var spinner = $('.spinner-border');
  spinner.hide();
  console.log('page loaded');
  $('.volunteer-btn').click(function(e) {
    e.preventDefault();
    var spinner = $(this).find('.spinner-border');
    var url = $(this).attr('href');

    console.log("Button clicked, showing spinner.");
    spinner.show();

    // Debug: Check spinner visibility
    console.log(spinner.css('display'));

    // Simulate delay before redirection
    setTimeout(function() {
      window.location.href = url;  // Redirect after a delay
    }, 2000);  // Delay in milliseconds
  })
});
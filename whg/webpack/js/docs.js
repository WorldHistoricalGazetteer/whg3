// Add smooth scrolling to the menu links

import '../css/docs.css';

$(document).ready(function(){
  // Adding smooth scroll on click
  $("#menu a").on('click', function(event) {
    if (this.hash !== "") {
      event.preventDefault();
      var hash = this.hash;
      $('html, body').animate({
        scrollTop: $(hash).offset().top
      }, 800, function(){
        window.location.hash = hash;
      });
    }
  });

  // Optional: Activate Bootstrap scrollspy to update sidebar active state on scroll
  $('body').scrollspy({target: "#menu"});
});


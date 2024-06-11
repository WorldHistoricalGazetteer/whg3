// Create a Bootstrap dialog contact form
import '../css/whg-modal.css';

function initWHGModal() {

	// Create the basic modal structure
	$('body').append(`
	  <div class="modal fade" id="whgModal" tabindex="-1" role="dialog" aria-labelledby="whgModalLabel" aria-hidden="true">
	    <div class="modal-dialog modal-lg modal-dialog-centered" role="document">
	      <div class="modal-content">
	      </div>
	    </div>
	  </div>
	`);

	$('[data-whg-modal]')
		.attr('data-bs-toggle', 'modal')
		.attr('data-bs-target', '#whgModal')
		.attr('href', '#')
		.addClass('text-decoration-none');

	$('#whgModal').on('show.bs.modal', function(e) {
		
		const url = $(e.relatedTarget).data('whg-modal');

		// Fetch HTML for modal
		$.ajax({
			url: url,
			method: 'GET',
			success: function(data) {
				// Load the fetched HTML content into the modal
				$('#whgModal .modal-content').html(data);

				// Initialize any CAPTCHA refresh functionality within the modal
				$('#whgModal').find('.captcha').click(function(e) {
					e.preventDefault();
					$.getJSON("/captcha/refresh/", function(result) {
						$('#id_captcha_0').val(result.key)
							.prev('img.captcha').attr('src', result.image_url);
					});
				});
				

                // Enable Bootstrap form validation using jQuery
                $('#whgModal form').on('submit', function (event) {
                    const captchaValid = validateCaptcha();
                    if (!this.checkValidity() || !captchaValid) {
                        event.preventDefault();
                        event.stopPropagation();
                    } else {
                        event.preventDefault(); // Prevent default form submission

                        // Append the current URL to the message text
                        $('#id_message').val(function(_, val) {
                            return val + ' [Sent from: ' + window.location.pathname + ']';
                        });

                        // Proceed with AJAX form submission
                        var formData = $(this).serialize();
                        $.ajax({
                            url: $(this).data('url'),
                            method: 'POST',
                            data: formData,
				            success: function(response) {
							    try {
							        // Try to parse the response as JSON
							        var responseData = JSON.parse(response);							
							        if (responseData.success) {
										// Hide inputs and show #confirmationMessage
                                        $('#whgModal .modal-body > div, #whgModal .modal-footer button').toggleClass('d-none');
							        } else {
						                alert('An error occurred while submitting the form.');
							        }
							    } catch (error) {
							        // If parsing as JSON fails, treat the response as HTML
							        $('#whgModal .modal-content').html(response);
							    }
				            },
                            error: function(xhr, status, error) {
                                alert('Sorry, there was an error submitting the form.');
                            }
                        });
                    }
                    $(this).addClass('was-validated');
                });

                // Custom validation function for captcha
                function validateCaptcha() {
                    var captchaInput = $('#whgModal .captcha-container input[type="text"]');
                    var captchaFeedback = $('#whgModal .captcha-container .invalid-feedback');
                    if (captchaInput.val().length !== 6) {
                        captchaInput.addClass('is-invalid');
                        captchaFeedback.show();
                        captchaInput[0].setCustomValidity('Invalid length');
                        captchaInput[0].reportValidity();
                        return false;
                    } else {
                        captchaInput.removeClass('is-invalid');
                        captchaFeedback.hide();
                        captchaInput[0].setCustomValidity('');
                        return true;
                    }
                }

				// Show the modal
				$('#whgModal').modal('show');
			},
			error: function(xhr, status, error) {
				alert('Sorry, there was an error loading the contact form.');
			}
		});
	});
	
	$('#whgModal').on('hidden.bs.modal', function(e) {
	    $('#whgModal .modal-content').html('');
	});

}

export {
	initWHGModal
};
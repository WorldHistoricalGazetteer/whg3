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

    $('#whgModal')
        .on('hidden.bs.modal', function (e) {
            $('#whgModal .modal-content').html('');
        })
        .on('show.bs.modal', function (e) {
            loadModalContent($(e.relatedTarget));
        });

    function loadModalContent(target) {
        const url = target.data('whg-modal');
        const modalSubject = target.data('subject');
        $.ajax({
            url: url,
            method: 'GET',
            success: function (data) {
                // Load the fetched HTML content into the modal
                var $content = $('#whgModal .modal-content');
                $content.html(data);

                if ($content.find('.modal-header').length === 0) {
                    $content
                        .wrapInner('<div class="modal-body"></div>')
                        .prepend(`
						<div class="modal-header">
						    <h5 class="modal-title">
								<img alt="WHG" height="38" src="/static/images/whg_logo.svg" width="50">
						    </h5>
						    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
						</div>		
					`);
                }

                if (modalSubject) {
                    $('#whgModal').find('input[name="subject"]').val(modalSubject);
                }

                // Content might itself have modal requirements
                $content.find('[data-whg-modal]')
                    .attr('href', '#')
                    .addClass('text-decoration-none')
                    .click(function () {
                        loadModalContent($(this));
                    });

                // Show the modal
                $('#whgModal').modal('show');
            },
            error: function (xhr, status, error) {
                alert('Sorry, there was an error loading the content.');
            }
        });
    }

    function validateTurnstile() {
        const responseField = document.querySelector('#whgModal [name="cf-turnstile-response"]');
        return responseField && responseField.value.trim().length > 0;
    }


    // Initialize any CAPTCHA refresh functionality within the modal
    $('body').on('click', '#whgModal form .captcha', function (e) { // Must delegate from body to account for form refresh on fail
        e.preventDefault();
        $.getJSON("/captcha/refresh/", function (result) {
            $('#id_captcha_0').val(result.key)
                .prev('img.captcha').attr('src', result.image_url);
        });
    });


    // Enable Bootstrap form validation using jQuery
    $('body').on('submit', '#whgModal form', function (event) { // Must delegate from body to account for form refresh on fail
        const $form = $(this);
        const turnstileValid = validateTurnstile();
        if (!this.checkValidity() || !turnstileValid) {
            event.preventDefault();
            event.stopPropagation();

            const turnstileContainer = $form.find('.turnstile-container');
            const feedback = turnstileContainer.find('.invalid-feedback');

            if (!turnstileValid) {
                feedback.text('Please verify that you are human.').addClass('d-block');
            } else {
                feedback.text('').removeClass('d-block');
            }
        } else {
            event.preventDefault(); // Prevent default form submission

            var formData = $form.serializeArray();
            formData.push({name: 'page_url', value: window.location.pathname});
            var formDataObject = {};
            formData.forEach(function (item) {
                formDataObject[item.name] = item.value;
            });

            $.ajax({
                url: $form.data('url'),
                method: 'POST',
                data: formDataObject,
                success: function (response, status, xhr) {
                    var contentType = xhr.getResponseHeader("content-type") || "";
                    if (contentType.includes("application/json")) {
                        if (response.success) {
                            // Hide inputs and show #confirmationMessage
                            $('#whgModal .modal-body > div, #whgModal .modal-footer button').toggleClass('d-none');
                        } else {
                            alert('An error occurred while submitting the form.');
                        }
                    } else {
                        // If the response is HTML, update the modal content
                        $form.remove();
                        $('#whgModal .modal-content').html(response);
                    }
                },
                error: function (xhr, status, error) {
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

}

export {
    initWHGModal
};
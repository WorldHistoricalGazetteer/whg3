// Create a Bootstrap error modal
import '../css/error-modal.css';

function errorModal(message, title, error, timeout) {

	// Create the basic modal structure
	$('body').append(`
        <div class="modal fade" id="errorModal" tabindex="-1" role="dialog" aria-labelledby="errorModalLabel" aria-hidden="true">
            <div class="modal-dialog" role="document">
                <div class="modal-content">
                    <div class="modal-header" style="background-color: red;">
                        <h5 class="modal-title" id="errorModalLabel">${title || "ERROR"}</h5>
                        <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                            <span aria-hidden="true">&times;</span>
                        </button>
                    </div>
                    <div class="modal-body">
                        <p>${message}</p>
                        ${ error && !!error.status ? `<p class="error">Status: ${error.status}</p>` : '' }
                        ${ error && !!error.statusText ? `<p class="error">Status Text: "${error.statusText}"</p>` : '' }
                        ${ error ? `<p class="error">See console log for more details.</p>` : '' }
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>
	`);
	
    $('#errorModal')
    .modal('show')
    .on('hidden.bs.modal', function () {
        $(this).remove();
    })
    .on('click', 'button.close, button.btn-secondary', function() {
		$('#errorModal').modal('hide');
	});
    
    if (timeout) {
        setTimeout(() => {
            $('#errorModal').modal('hide');
        }, timeout * 1000);
    }

}

export { errorModal };
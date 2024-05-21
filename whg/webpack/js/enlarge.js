// Create a Bootstrap dialog containing a clicked image

$.fn.enlarge = function() {
    this.on('click', function() {
        const imgClone = $(this).clone().removeClass().css({'max-width': '80vw', 'max-height': '80vh', cursor: 'pointer'});
        const closeButton = $('<button type="button" class="btn-close" aria-label="Close"></button>').css({position: 'absolute', 'background-color': 'white', right: '1.2em', top: '1.2em', 'z-index': '999'});
        const modalBody = $('<div class="modal-body"></div>').append(imgClone);
        const modalContent = $('<div class="modal-content"></div>').css({width: 'fit-content', height: 'fit-content'}).append(closeButton, modalBody);
        const modalDialog = $('<div class="modal-dialog"></div>').css({'max-width': '100vw', 'max-height': '100vh'}).append(modalContent);
        const modal = $('<div class="modal fade"></div>').append(modalDialog);
        
        closeButton.on('click', function() {
            modal.modal('hide');
        });

        modal.on('hidden.bs.modal', function() {
            modal.remove();
        });

        imgClone.on('load', function() {
        	modal.modal('show');
        });
    }).attr('data-bs-toggle', 'tooltip').attr('data-bs-title', 'Click to enlarge');
};

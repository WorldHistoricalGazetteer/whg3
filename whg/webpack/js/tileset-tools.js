import '../css/tileset-tools.css';

$(document).ready(function() {
	let data = JSON.parse($('#data').text());
	let pollCount = 0;

	// Function to populate the table
	function populateTable() {
		pollCount = data.length;
		let tableBody = $('#tileset-table tbody');
		let previousCategory
		data.forEach(function(item) {
			// Add a row separator if the current item's category is different from the previous item's category
			if (item.category !== previousCategory) {
				tableBody.append(`<tr class="row-separator"><td colspan="5">${item.category.toUpperCase()}</td></tr>`);
			}
			let row = $('<tr>');
			row.addClass(item.category === 'datasets' ? 'dataset-row' : 'collection-row');
			if (!item.public) row.addClass('unpublished');
			row.append($('<td>').text(item.id));
			row.append($('<td>').text(item.title));
			row.append($('<td>')
			.html(`<i data-bs-toggle="tooltip" data-bs-title="Click to inspect tileset"${item.has_tileset ? '' : ' disabled'} class="has-tileset fas fa-${item.has_tileset ? 'check' : 'times'}" data-category="${item.category}" data-id="${item.id}"></i>`))
			.find('i.fa-check').tooltip();
			row.append($('<td>').html(`<i class="fas ${item.task_id ? 'fa-spinner fa-spin' : 'fa-times'}"></i>`)); // Placeholder for pending status
			row.append($('<td>').text('')); // Placeholder for actions
			tableBody.append(row);

			// Start polling task status for `needs tileset`
			pollTaskStatus(item.task_id, row, item);
			previousCategory = item.category;
		});
	    var queueAllButton = $('<button>')
	    .text('Queue All')
	    .addClass('queue-all btn btn-warning btn-sm')
	    .prop('disabled', true)
	    .attr('data-bs-toggle', 'tooltip')
	    .attr('data-bs-title', 'Queue the generation or deletion of all required or redundant tilesets');
	    $('#tileset-table th:last').append(queueAllButton);
	}

	populateTable();

	// Define a function to poll task status for needs tileset recursively
	function pollTaskStatus(taskId, row, item, attempt = 0) {
		function lowerPollcount() {
			pollCount--;
			$('.queue-all').prop('disabled', pollCount > 0);
		}
		if (!taskId) {
			lowerPollcount();
			return;
		}
		// Fetch task status
		fetch(`/task_progress/${taskId}`)
			.then(response => {
				if (response.ok) {
					return response.json().catch(() => {
						// If parsing fails, it's not JSON
						return response.text().then(text => {
							console.error('Non-JSON response:', text);
							throw new Error('Received non-JSON response');
						});
					});
				} else {
					return response.text().then(text => {
						console.error('Fetch error:', text);
						throw new Error('Fetch error');
					});
				}
			})
			.then(result => {
				if (result.state === 'PENDING' && attempt < 60) { // Stop after 60 attempts
					// Continue polling
					setTimeout(() => pollTaskStatus(taskId, row, item, attempt + 1), 5000); // Poll every 5 seconds
				} else if (result.state === 'SUCCESS') {
					lowerPollcount();
					//console.log('result.progress', result.progress)
					item.needs_tileset = result.progress[0] == true;
	                let detailHTML = `
	                    <div>
	                        <strong>Total Coordinates:</strong> ${result.progress[1]}<br>
	                        <strong>Total Geometries:</strong> ${result.progress[2]}<br>
	                        <strong>Total Places:</strong> ${result.progress[3]}<br>
	                    </div>
	                `;
					row
					.find('td:eq(3) i')
					.removeClass('fa-spinner fa-spin')
					.addClass(item.needs_tileset ? 'fa-check' : 'fa-times')
	    			.attr('data-bs-toggle', 'tooltip')
					.attr('data-bs-title', detailHTML);
					addButtons(item, row);
				} else {
					lowerPollcount();
					// If task fails or has other states, update the needs tileset column accordingly
					row.find('td:eq(3) i')
					.removeClass('fa-spinner fa-spin')
					.addClass('exclamation-circle');
				}
			})
			.catch(error => console.error(error));
	}

	// Function to add buttons based on item data and task result
	function addButtons(item, row) {
		// Clear existing buttons
		row.find('td:eq(4)').empty();

		// Check if the item has a tileset and needs it
		if (item.has_tileset && item.needs_tileset) {
			// Item has tileset and needs it
			row.find('td:eq(4)').append(`<button data-bs-toggle="tooltip" data-bs-title="Click to queue removal of this tileset" class="btn btn-primary btn-sm tileset-available" data-category="${item.category}" data-id="${item.id}">Tileset Available</button>`);
		} else if (item.has_tileset) {
			// Item has tileset but doesn't need it
			row.find('td:eq(4)').append(`<button data-bs-toggle="tooltip" data-bs-title="Click to queue removal of this tileset" class="btn btn-warning btn-sm remove-redundant" data-category="${item.category}" data-id="${item.id}">Remove Redundant</button>`);
		} else if (item.needs_tileset) {
			// Item doesn't have tileset but needs it
			row.find('td:eq(4)').append(`<button data-bs-toggle="tooltip" data-bs-title="Click to queue generation of a tileset" class="btn btn-success btn-sm generate-tileset" data-category="${item.category}" data-id="${item.id}">Generate Tileset</button>`);
		} else {
			// Item doesn't have tileset and doesn't need it
			row.find('td:eq(4)').append(`<button data-bs-toggle="tooltip" data-bs-title="Click to queue generation of a tileset" class="btn btn-secondary btn-sm no-tileset" data-category="${item.category}" data-id="${item.id}">No Action</button>`);
		}
	}
	
	let polling = false;
	function pollTilerStatus() {
		polling = true;
    	var tasks = [];
		$('button.processing').each(function() {
		    var category = $(this).data('category');
		    var id = $(this).data('id');
		    var action = $(this).hasClass('generate-tileset') ? 'generate' : 'delete';
		    tasks.push({ category: category, id: id, action: action });
		});
		
		console.log('polling tasks', tasks);
		
		if (tasks.length > 0) {
		    $.ajax({
		        url: '/tileset_task_progress/',
		        type: 'POST',
		        headers: { 'X-CSRFToken': csrfToken },
		        contentType: 'application/json',
		        data: JSON.stringify(tasks),
		        success: function(response) {
					
				    response.forEach(function(task) {
				        var taskButton = $(`button.${ task.action == 'generate' ? 'generate-tileset' : 'remove-redundant' }[data-category="${task.category}"][data-id="${task.id}"]`);
				        var buttonIcon = taskButton.find('i.fas');
				        if (taskButton.length > 0) {
				            // Update UI based on task progress
				            switch (task.progress) {
				                case 'queued':
				                    break;
				                case 'pending':
									buttonIcon
									.removeClass('fa-hourglass-half')
									.addClass('fa-spinner fa-spin');
				                    break;
				                case 'success':
				                    taskButton
				                    .removeClass('processing generate-tileset remove-redundant')
				                    .addClass(`${task.action == 'generate' ? 'tileset-available' : 'no-tileset'}`)
				                    .html(`${task.action == 'generate' ? 'Generation' : 'Removal'} OK`)
				                    .tooltip('dispose')
				                    .attr('data-bs-title', `${task.action == 'generate' ? 'Click to queue removal of this tileset' : 'Click to queue generation of a tileset'}`)
				                    .tooltip()
				                    .prop('disabled', false)
				                    .closest('tr')
				                    .find('td:eq(2) i')
					                .toggleClass('fa-times fa-check')
					                .filter('.fa-times')
					                .tooltip('dispose')
					                .end()
					                .filter('.fa-check')
					                .tooltip();
				                    break;
				                case 'failed':
				                    taskButton
				                    .removeClass('processing btn-info')
				                    .addClass('btn-danger')
				                    .prop('disabled', false)
				                    .tooltip()
				                    .html(`${task.action == 'generate' ? 'Generation' : 'Removal'} Failed`);
				                    break;
				                default:
				                    break;
				            }
				        }
				    });
					
		            //Start polling task status
		            setTimeout(pollTilerStatus, 3000);
		        },
		        error: function(xhr, status, error) {
		            console.error(xhr.responseText);
		        }
		    });
		}
		else polling = false;
	}

    $('#tileset-table')
    .on('click', 'i.has-tileset.fa-check', function() {
		const el = $(this);
	    var category = el.data('category');
	    var id = el.data('id');
	    var url = el.data('url');
	    if (!url) {
		    $.getJSON(`${process.env.TILEBOSS}/data/${category}-${id}.json`, function(tilejson) {
		        var center = tilejson.center;
		        url = `${process.env.TILEBOSS}/data/${category}-${id}/#${center[2]}/${center[1]}/${center[0]}`;
		        el.data('url', url);
		        window.open(url, '_blank');
		    });
		}
		else {
			window.open(url, '_blank');
		}
    })
    .on('click', '.tileset-available', function() {
		$(this)
		.removeClass('btn-primary tileset-available')
		.addClass('btn-warning remove-redundant')
		.click();
    })
	.on('click', '.no-tileset', function() {
		$(this)
		.removeClass('btn-secondary no-tileset')
		.addClass('btn-success generate-tileset')
		.click();
    })
	.on('click', '.generate-tileset, .remove-redundant', function() {
		let button = $(this);
        let category = button.data('category');
        let id = button.data('id');
        let action = button.hasClass('generate-tileset') ? 'generate' : 'delete'; // Determine the action based on the button class
	            
        button
        .tooltip('dispose')
        .removeClass('btn-success')
        .addClass('btn-info processing')
        .prop('disabled', true)
        .html(`<i class="fas fa-hourglass-half"></i> ${action == 'generate' ? 'Generating' : 'Removing'}`);

        $.ajax({
            url: `/tileset_generate/${category}/${id}/?action=${action}`,
            type: action === 'generate' ? 'GET' : 'DELETE',
			headers: {
				'X-CSRFToken': document.querySelector(
					'[name=csrfmiddlewaretoken]').value,
			},
            success: function(response) {
	            if (!polling) pollTilerStatus();
            },
            error: function(xhr, status, error) {
                console.error(xhr.responseText);
            }
        });
        
		setTimeout(function(){if (!polling) pollTilerStatus();}, 3000);
    });	

    $('.queue-all').click(function() {
        $('.generate-tileset, .remove-redundant').each(function() {
            $(this).click();
        });
    });    

});
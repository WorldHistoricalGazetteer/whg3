// builders-dataset-status.js

import '../css/builders-dataset-status.css';

$(function() {
	
	$("[data-toggle=popover]").popover({
		html: true
	})

	// help modals
	$(".help-matches").click(function() {
		page = $(this).data('id')
		console.log('help:', page)
		$('.selector').dialog('open');
	})
	$(".selector").dialog({
		resizable: false,
		autoOpen: false,
		height: $(window).height() * 0.6,
		width: $(window).width() * 0.5,
		title: "WHG Help",
		modal: true,
		buttons: {
			'Close': function() {
				console.log('close dialog');
				$(this).dialog('close');
			}
		},
		open: function(event, ui) {
			$('#helpme').load('/media/help/' + page + '.html')
		},
		show: {
			effect: "fade",
			duration: 400
		},
		hide: {
			effect: "fade",
			duration: 400
		}
	});

	if (context_status == 'updating') {
		console.log(context_status, context_context)
		$("#ds_info").addClass('hidden')
		$("#ds_updating").removeClass('hidden')
		$("#div_file").toggleClass('border-red')
		$(".update-msg").removeClass('hidden')
	}

	window.dslabel = context_dsLabel
	
	// ******************* LISTENERS *******************   

	$(".feedback").click(function() {
		console.log(clicked)
		url = window.location.href = "/contact?from=" + clicked
		window.location.href = url
		console.log('gwine to contact form, from clicked', url)
	})
	
	// views_dl.downloader()
	$(".a-dl-celery").click(function(e) {
		e.preventDefault()
		// startDownloadSpinner()
		console.log('sending post')
		console.time('dl')
		format = $(this).attr('ref')
		dsid = context_dsid
		console.log('send to downloader()')
		urly = '/dlcelery/'
		$.ajax({
			type: 'POST',
			headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value },
			url: urly,
			data: {
				"format": format,
				"dsid": dsid,
			},
			datatype: 'json',
			success: function(response) {
				startDownloadSpinner()
				console.log('got task_id', response)
				task_id = response.task_id
				var progressUrl = "/celery-progress/" + task_id + "/";
				CeleryProgressBar.initProgressBar(progressUrl, {
					pollingInterval: 500,
					onResult: customResult,
				})
			}
		})
	})
    
    $('#year_filter').change(function() {
        var isChecked = $(this).prop('checked');
        $.ajax({
            url: '/datasets/update_vis_parameters/',
            method: 'POST',
			headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value },
            data: {
                'checked': isChecked,
                'ds_id': context_dsid
            },
            success: function(response) {
				console.log(response.message);
            },
            error: function(xhr, status, error) {
                // If the AJAX call fails, reset the checkbox state
                $('#year_filter').prop('checked', !isChecked);
                alert('Sorry, failed to update visualisation parameters.');
            }
        });
    });	
	
	$("#a_update_modal").on('click', function(e) {
		console.log('clicked update')
		if (context_format != 'delimited') {
			alert('Sorry, update is available only for delimited files right now. Soon...')
		}
	})
	
	// show upload button after file selected
	$("#newfile").on("change", function() {
		$("#btn_upload").removeClass('hidden')
	});
	
	$("#btn_done").on('click', function() {
		location.reload();
	})
	$("#btn_cancel").on('click', function() {
		location.reload();
	})
	
	// TODO: refactor this unholy mess
	// also, button is hidden on 2nd click
	$(".edit-title").click(function() {
		$(".editing-title").toggleClass("hidden")
		$(".form-title").toggleClass("hidden")
		$(".btn-ds").toggleClass("hidden")
	})
	$(".edit-description").click(function() {
		$(".editing-description").toggleClass("hidden")
		$(".form-description").toggleClass("hidden")
		$(".btn-ds").toggleClass("hidden")
	})
	$(".edit-public").click(function() {
		console.log('edit-public')
		$(".editing-public").toggleClass("hidden")
		$(".form-public").toggleClass("hidden")
		$(".btn-ds").toggleClass("hidden")
	})
	$(".edit-creator").click(function() {
		$(".editing-creator").toggleClass("hidden")
		$(".form-creator").toggleClass("hidden")
		$(".btn-ds").toggleClass("hidden")
	})
	$(".edit-source").click(function() {
		$(".editing-source").toggleClass("hidden")
		$(".form-source").toggleClass("hidden")
		$(".btn-ds").toggleClass("hidden")
	})
	$(".edit-contrib").click(function() {
		$(".editing-contrib").toggleClass("hidden")
		$(".form-contrib").toggleClass("hidden")
		$(".btn-ds").toggleClass("hidden")
	})
	$(".edit-citation").click(function() {
		$(".editing-citation").toggleClass("hidden")
		$(".form-citation").toggleClass("hidden")
		$(".btn-ds").toggleClass("hidden")
	})
	$(".edit-uri_base").click(function() {
		$(".editing-uri_base").toggleClass("hidden")
		$(".form-uri_base").toggleClass("hidden")
		$(".btn-ds").toggleClass("hidden")
	})
	$(".edit-webpage").click(function() {
		$(".editing-webpage").toggleClass("hidden")
		$(".form-webpage").toggleClass("hidden")
		$(".btn-ds").toggleClass("hidden")
	})
	$(".edit-featured").click(function() {
		$(".editing-featured").toggleClass("hidden")
		$(".form-featured").toggleClass("hidden")
		$(".btn-ds").toggleClass("hidden")
	})
	$(".edit-image").click(function() {
		$(".editing-image").toggleClass("hidden")
		$(".form-image").toggleClass("hidden")
		$(".btn-ds").toggleClass("hidden")
	})
	$(".edit-pdf").click(function() {
		$(".editing-pdf").toggleClass("hidden")
		$(".form-pdf").toggleClass("hidden")
		$(".btn-ds").toggleClass("hidden")
	})
	
	// ******************* FUNCTIONS *******************
	
	let dater = function() {
		const date = new Date(Date.now());
		return date.toISOString().substring(0, 10)
	}
	
	let clearEl = function(el) {
		$("#progress-bar").fadeOut()
		el.html('')
	}
	
	// post-download actions
	function customResult(resultElement, result) {
		console.log('celery result', result)
		console.log('celery resultElement', resultElement)
		spinner_dl.stop()
		fn = result.filename
		link = '[ <span class="dl-save"><a href="/' + fn + '" title="downloaded: ' + dater() +
			'" download>save</a></span> ]'
		$(resultElement).append(
			$('<p>').html(link)
		);
		$(".dl-save a")[0].click()
		setTimeout(clearEl($("#celery-result")), 1000)
	}
	
	function startUpdateSpinner() {
		window.spinner_update = new Spin.Spinner().spin();
		$("#update_spinner").append(spinner_update.el);
	}
	
	function startDownloadSpinner() {
		window.spinner_dl = new Spin.Spinner().spin();
		$("#ds_downloads").append(spinner_dl.el);
	}
	
	// parse & prettify ds_update() results
	// [status,format,update_count,redo_count,new_count,deleted_count,newfile]
	function updateText(data) {
		html = 'Changes in database: <br/>' + '<ul>' +
			'<li>Added ' + data["new_count"] + ' rows </li>' +
			'<li>Deleted ' + data["deleted_count"] + ' rows </li>' +
			'<li>Updated ' + data["update_count"] + ' rows </li>' + '</ul>'
		html += 'A followup reconciliation to Wikidata task is required.'
	
		if (data['indexed'] == true) {
			html += ', as well as a reindexing, in order to account for these changes.'
		}
		return html
	}

})

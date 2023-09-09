export default function generateMapImage(map, dpi = 300, fileName = 'WHG_Map') {

	// Create a modal dialog for copyright attribution and acknowledgment
	const modal = $('<div id="map-download-dialog" title="Map Attribution"></div>');
	const injunctionText = $('<div id="injunction-text" class="injunction-text">The following attribution must be displayed together with any use of this map image:</div>');
	const attributionText = $('<div id="attribution-text" class="attribution-text"></div>');
	const downloadButton = $('<button id="download" style="display: none;" disabled>...rendering...</button>');
	const copyAttributionButton = $('<button id="copy-attribution">Acknowledge and Copy Attribution</button>');
	const cancelButton = $('<button id="cancel">Cancel</button>');

	// Add the missing paragraph
	modal.append(injunctionText);
	modal.append(attributionText);
	modal.append(copyAttributionButton);
	modal.append(downloadButton);
	modal.append(cancelButton);

	// Create a dialog with the modal content
	modal.dialog({
		autoOpen: false,
		appendTo: '#map',
		modal: true,
		width: 'auto',
		buttons: [],
		closeOnEscape: false,
		open: function() {
			const style = map.getStyle();
			if (style && style.sources) {
				const sources = style.sources;
				const attributions = [];
				Object.keys(sources).forEach((sourceName) => {
					const source = sources[sourceName];
					if (source.attribution) {
						const tempElement = document.createElement('div');
						tempElement.innerHTML = source.attribution;
						const displayedText = tempElement.textContent;
						attributions.push(displayedText);
					}
				});
				const fullAttributionText = attributions.join('\n');
				attributionText.text(fullAttributionText);
			}
		},
	});

	// Copy attribution text to clipboard when the button is clicked
	copyAttributionButton.on('click', () => {
		const textToCopy = attributionText.text();

		if (navigator.clipboard) {
			navigator.clipboard.writeText(textToCopy)
				.then(() => {
					alert('Attribution text copied to clipboard.');
					// Make the "Download" button visible after copying
					downloadButton.show();
				})
				.catch(err => {
					console.error('Unable to copy attribution text: ', err);
				});
		} else {
			// Fallback for browsers that do not support the Clipboard API
			const tempInput = $('<textarea>');
			tempInput.val(textToCopy);
			$('body').append(tempInput);
			tempInput.select();
			document.execCommand('copy');
			tempInput.remove();
			alert('Attribution text copied to clipboard (fallback).');
			// Make the "Download" button visible after copying
			downloadButton.show();
		}
	});

	const originalCanvas = map.getCanvas();
	const width = originalCanvas.width;
	const height = originalCanvas.height;

	// Store the actual devicePixelRatio
	const actualPixelRatio = window.devicePixelRatio;
	// Set the devicePixelRatio for higher DPI rendering
	Object.defineProperty(window, 'devicePixelRatio', {
		get: function() {
			return dpi / 96;
		},
	});
	console.log(actualPixelRatio, window.devicePixelRatio);

	// Create a hidden container for rendering the map
	const originalMapContainer = originalCanvas.parentNode;
	const container = document.createElement('div');
	container.id = 'map-render-container';
	container.style.width = width + 'px';
	container.style.height = height + 'px';
	originalMapContainer.appendChild(container);

	// Create a map renderer
	const renderMap = new maptilersdk.Map({
		container: container,
		style: map.getStyle(),
		center: map.getCenter(),
		zoom: map.getZoom(),
		bearing: map.getBearing(),
		pitch: map.getPitch(),
		interactive: false,
		preserveDrawingBuffer: true,
		fadeDuration: 0,
		attributionControl: false,
		transformRequest: map._requestManager._transformRequestFn,
	});

	renderMap.once('idle', () => {
		downloadButton.prop('disabled', false).text('Download');
	});

	// Download button event handler
	downloadButton.on('click', () => {
		const canvas = renderMap.getCanvas();
		const imageFileName = `${fileName}.png`;

		// Create a download link for the image
		const a = $('<a>');
		a.prop('href', canvas.toDataURL());
		a.prop('download', imageFileName);
		a[0].click();
		a.remove();

		cleanUp();
	});

	function cleanUp() {
		renderMap.remove();
		container.remove();
		/*	  Object.defineProperty(window, 'devicePixelRatio', {
			    get: function () {
			      return actualPixelRatio;
			    },
			  });*/
		modal.dialog('close');
		modal.remove();

	}

	// Cancel button event handler
	cancelButton.on('click', () => {
		cleanUp();
	});

	// Open the dialog
	modal.dialog('open');
}
// whg/webpack/js/mapParameters.js

const styles = {
    'ne_global': {
        version: 8,
        sources: {
            basemap: {
                type: 'raster',
                tiles: [
                    mbtoken ? `https://a.tiles.mapbox.com/v4/kgeographer.ne_global/{z}/{x}/{y}.png?access_token=${mbtoken}` : '',
                    mbtoken ? `https://b.tiles.mapbox.com/v4/kgeographer.ne_global/{z}/{x}/{y}.png?access_token=${mbtoken}` : ''
                ],
                tileSize: 256,
            },
        },
        layers: [{
            id: 'basemap',
            type: 'raster',
            source: 'basemap',
        }]        
    },
}

class mapParams {
    constructor({
		style = 'OUTDOOR.DEFAULT',
		container = 'map',
		center = [9.2, 33],
        zoom = 0.2,
        minZoom = 0.1,
        maxZoom = 10,
        attributionControl = true,
        attributionControlOpen = false,
        fullscreenControl = false,
        geolocateControl = false,
        navigationControl = true,
        sequencerControl = false,
        temporalControl = false,
        userProperties = true,
        bearing = 0,
        pitch = 0,
		} = {}) {
        this.style = this.setStyle(style);
        this.container = container;
        this.center = center;
        this.zoom = zoom;
        this.minZoom = minZoom;
        this.maxZoom = maxZoom;
        this.attributionControl = attributionControl;
        this.attributionControlOpen = attributionControlOpen;
        this.fullscreenControl = fullscreenControl;
        this.geolocateControl = geolocateControl;
        this.layerControl = Array.isArray(style);
        this.navigationControl = navigationControl;
        this.sequencerControl = sequencerControl;
        this.temporalControl = this.setTemporalControl(temporalControl);
        this.userProperties = userProperties;
        this.bearing = bearing;
        this.pitch = pitch;
    }

    setStyle(style) {
        if (Array.isArray(style)) {
            let styleCode = style[0].split('.');
            return maptilersdk.MapStyle[styleCode[0]][styleCode[1]];
        }
        return styles[style];
    }

    setTemporalControl(temporalControl) {
        if (temporalControl===true) { // Set default values; for other values pass an object containing all of these parameters
            return {
                fromValue: 1550,
                toValue: 1720,
                minValue: -2000,
                maxValue: 2100,
                open: false,
                includeUndated: true, // null | false | true - 'false/true' determine state of select box input; 'null' excludes the button altogether
                epochs: null,
                automate: null,
			};
        }
        return temporalControl;
    }
}

maptilersdk.config.apiKey = `${ !!maptilerkey ? maptilerkey : "" }`;

export default mapParams;

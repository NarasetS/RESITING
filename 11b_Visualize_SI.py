import xarray as xr
import hvplot.xarray
import holoviews as hv
from pathlib import Path

def generate_interactive_si_maps():
    print("Starting Interactive Map Generation with hvplot...")

    output_dir = Path("Output")
    
    # Define the criteria and their corresponding files/variables
    # Format - Display Name: (filename, variable_template)
    criteria_files = {
        'Final Weighted SI': ('xr_final_SI_all.nc', 'SI_{t}'),
        '0. Landcover': ('xr_SI_Landcover.nc', 'SI_{t}'),
        '1. Slope': ('xr_SI_Slope.nc', 'SI_{t}'),
        '2. Elevation': ('xr_SI_Elevation.nc', 'SI_{t}'),
        '3. Dist to Settlement': ('xr_SI_Distancetosettlementarea.nc', 'SI_{t}'),
        '4. Dist to Wetland': ('xr_SI_Distancetowetland.nc', 'SI_{t}'),
        '5. Dist to Forest': ('xr_SI_Distancetoforest.nc', 'SI_{t}'),
        '6. Dist to Road': ('xr_SI_Distancetoroad.nc', 'SI_{t}'),
        '7. Dist to Substation': ('xr_SI_Distancetosubstation.nc', 'SI_DtoSubs'),
        '8. Resource Potential': ('xr_SI_resourcepotential.nc', 'SI_{t}'),
        '9. Land Cost': ('xr_SI_LandCost.nc', 'land_cost_avg_price_norm'),
        '10. Farm/Feedstock Area': ('xr_SI_Farmarea.nc', 'SI_{t}'),
    }
    
    techs = ['Wind', 'Solar', 'Biomass', 'BGEC', 'BGWW', 'MSW', 'IEW']

    for tech in techs:
        print(f"Generating interactive map for {tech}...")
        
        tech_plots = {}
        for crit_name, (fname, var_tpl) in criteria_files.items():
            fpath = output_dir / fname
            if not fpath.exists():
                print(f"  -> Missing {fname}, skipping {crit_name}...")
                continue
            
            var_name = var_tpl.format(t=tech)
            ds = xr.open_dataset(fpath)
            
            if var_name in ds.data_vars:
                # Mask out zeros so the OpenStreetMap tiles show through unavailable areas
                data = ds[var_name]
                si_masked = data.where(data > 0)
                
                plot = si_masked.hvplot.image(
                    x='lon', y='lat', 
                    geo=True, tiles='OSM', cmap='viridis', 
                    title=f"{tech} - {crit_name}",
                    frame_width=600, frame_height=800, alpha=0.7
                )
                tech_plots[crit_name] = plot
            
            ds.close() # Close to conserve memory
            
        if tech_plots:
            # Combine all plots into a HoloMap (creates a dropdown UI)
            holo_map = hv.HoloMap(tech_plots, kdims='Criteria')
            
            out_path = output_dir / f"Interactive_{tech}_SI.html"
            hv.save(holo_map, str(out_path))
            print(f"Saved: {out_path}")

    print("All interactive maps generated successfully!")

if __name__ == "__main__":
    generate_interactive_si_maps()
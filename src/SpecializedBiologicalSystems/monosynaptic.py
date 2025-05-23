from brian2 import *
from .base_system import BiologicalSystem


class Monosynaptic(BiologicalSystem):
    """
    Specialized class for monosynaptic reflexes.
    
    Monosynaptic reflexes involve a direct connection from afferent (Ia) neurons
    to motor neurons (MN) without intermediate interneurons.
    """
    
    def __init__(self, reaction_time=25*ms, biophysical_params=None, muscles_names=None, 
                associated_joint="ankle_angle_r", custom_neurons=None, custom_connections=None, 
                custom_spindle=None, ees_recruitment_profile=None, fast_type_mu=True,
                custom_initial_potentials=None, custom_initial_condition_spike_activation=None, 
                initial_state_opensim=None):
        """
        Initialize a monosynaptic reflex system with default or custom parameters.
        """
        # Set default parameters if not provided
        if muscles_names is None:
            muscles_names = ["soleus_r"]
            
        if biophysical_params is None:
            biophysical_params = {
                'T_refr': 5 * ms,  # Refractory period
                'Eleaky': -70*mV,
                'gL': 10*nS,
                'Cm': 0.3*nF,  
                'E_ex': 0*mV,
                'tau_e': 0.5*ms,
                'threshold_v': -50*mV
            }
            
        if ees_recruitment_profile is None:
            ees_recruitment_profile = {
                'Ia': {
                    'threshold_10pct': 0.3,  # Normalized current for 10% recruitment
                    'saturation_90pct': 0.7  # Normalized current for 90% recruitment
                },
                'MN': {
                    'threshold_10pct': 0.7,  # Motoneurons are recruited at high intensity
                    'saturation_90pct': 0.9  
                }
            }
            
        # Initialize the base class
        super().__init__(reaction_time, ees_recruitment_profile, biophysical_params, 
                        muscles_names, associated_joint, fast_type_mu, initial_state_opensim)
        
        # Set default neuron populations
        self.neurons_population = {
            "Ia": 410,       # Type Ia afferent neurons
            "MN": 500       # Motor neurons
        }
        
        # Override with custom values if provided
        if custom_neurons is not None:
            self.neurons_population.update(custom_neurons)
            
        # Set default connections
        self.connections = {
            ("Ia", "MN"): {"w": 2.1*nS, "p": 0.7}
        }
        
        # Override with custom connections if provided
        if custom_connections is not None:
            self.connections.update(custom_connections)
            
        # Set default spindle model
        self.spindle_model = {
            "Ia": "10+ 2*stretch + 4.3*sign(stretch_velocity)*abs(stretch_velocity)**0.6"
        }
        
        # Override with custom spindle model if provided
        if custom_spindle is not None:
            self.spindle_model.update(custom_spindle)

        self.initial_potentials = {
            "MN": self.biophysical_params['Eleaky']
        }
        if custom_initial_potentials is not None:
            self.initial_potentials = custom_initial_potentials
            
        # Initialize parameters for each motoneuron
        self.initial_condition_spike_activation = [
            [{
                'u0': [0.0, 0.0],    # Initial fiber AP state
                'c0': [0.0, 0.0],    # Initial calcium concentration state
                'P0': 0.0,           # Initial calcium-troponin binding state
                'a0': 0.0            # Initial activation state
            } for _ in range(self.neurons_population['MN'])]
        ]
        if custom_initial_condition_spike_activation is not None:   
            self.initial_condition_spike_activation = custom_initial_condition_spike_activation
        
        # Validate parameters
        self.validate_input()

    def validate_input(self):
        """
        Validates the configuration parameters for monosynaptic reflex system.
        
        Raises:
            ValueError: If critical errors are found in the configuration
        """
        issues = {"warnings": [], "errors": []}
        
        # Check muscle count (should be 1 for monosynaptic)
        if self.number_muscles != 1:
            issues["errors"].append("Monosynaptic reflex should have exactly 1 muscle")
        
        # Check required neuron types
        required_neurons = {"Ia", "MN"}
        defined_neurons = set(self.neurons_population.keys())
        
        missing_neurons = required_neurons - defined_neurons
        if missing_neurons:
            issues["errors"].append(f"Missing required neuron types for monosynaptic reflex: {missing_neurons}")
        
        # Check for unexpected neuron types
        unexpected_neurons = defined_neurons - required_neurons
        if unexpected_neurons:
            issues["warnings"].append(f"Unexpected neuron types for monosynaptic reflex: {unexpected_neurons}")
        
        # Check connections
        required_connections = {("Ia", "MN")}
        defined_connections = set(self.connections.keys())
        
        missing_connections = required_connections - defined_connections
        if missing_connections:
            issues["errors"].append(f"Missing required connections for monosynaptic reflex: {missing_connections}")
        
        # Check spindle model
        if "Ia" not in self.spindle_model:
            issues["errors"].append("Missing Ia equation in spindle model for monosynaptic reflex")
        
        # Check EES recruitment parameters
        for neuron_type in ["Ia", "MN"]:
            if neuron_type not in self.ees_recruitment_profile:
                issues["errors"].append(f"Missing EES recruitment parameters for neuron type '{neuron_type}'")
        
        # Check biophysical parameters (no inhibitory parameters should be present)
        if "E_inh" in self.biophysical_params or "tau_i" in self.biophysical_params:
            issues["warnings"].append("Inhibitory parameters present but no inhibitory neurons in monosynaptic reflex")
        
        # Check mandatory biophysical parameters
        required_params = ['T_refr', 'Eleaky', 'gL', 'Cm', 'E_ex', 'tau_e', 'threshold_v']
        for param in required_params:
            if param not in self.biophysical_params:
                issues["errors"].append(f"Missing mandatory biophysical parameter: '{param}'")
        
        # Check units
        expected_units = {
            'T_refr': second,
            'Eleaky': volt,
            'gL': siemens,  
            'Cm': farad,
            'E_ex': volt,
            'tau_e': second,
            'threshold_v': volt
        }
        
        for param, expected_unit in expected_units.items():
            if param in self.biophysical_params:
                value = self.biophysical_params[param]
                if not value.dim == expected_unit.dim:
                    issues["errors"].append(
                        f"Parameter '{param}' has incorrect unit. "
                        f"Expected unit compatible with {expected_unit}, but got {value.unit}"
                    )
        
        # Validate EES parameters
        for neuron_type, params in self.ees_recruitment_profile.items():
            if neuron_type in ["Ia", "MN"]:
                required_ees_params = ["threshold_10pct", "saturation_90pct"]
                for param in required_ees_params:
                    if param not in params:
                        issues["errors"].append(f"Missing '{param}' in EES recruitment parameters for '{neuron_type}'")
                
                if "threshold_10pct" in params and "saturation_90pct" in params:
                    threshold = params['threshold_10pct']
                    saturation = params['saturation_90pct']
                    
                    if not (0 <= threshold <= 1) or not (0 <= saturation <= 1):
                        issues["errors"].append(
                            f"EES parameters for '{neuron_type}' must be between 0 and 1. "
                            f"Got: threshold={threshold}, saturation={saturation}"
                        )
                    if threshold >= saturation:
                        issues["errors"].append(f"Threshold must be less than saturation for '{neuron_type}'")
        
        # Raise error if there are critical issues
        if issues["errors"]:
            error_messages = "\n".join(issues["errors"])
            raise ValueError(f"Monosynaptic configuration errors:\n{error_messages}")
        
        # Print warnings if any
        if issues["warnings"]:
            warning_messages = "\n".join(issues["warnings"])
            print(f"WARNING: Monosynaptic configuration issues:\n{warning_messages}")
            
        return True

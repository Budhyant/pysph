"""Hydrostatic tank examples (Section 6.0) of Adami et. al. JCP 231, 7057-7075"""

# PyZoltan imports
from pyzoltan.core.carray import LongArray

# PySPH imports
from pysph.base.utils import get_particle_array
from pysph.base.kernels import Gaussian, WendlandQuintic, CubicSpline
from pysph.solver.solver import Solver
from pysph.solver.application import Application
from pysph.sph.integrator import TransportVelocityStep, Integrator

# the eqations
from pysph.sph.equation import Group
from pysph.sph.wc.basic import BodyForce
from pysph.sph.wc.transport_velocity import DensitySummation,\
    SolidWallBC, MomentumEquation, StateEquation, ArtificialStress

# numpy
import numpy as np

# domain and reference values
Lx = 2.0; Ly = 1.0; H = 0.9
gy = -1.0
Vmax = np.sqrt(2*abs(gy) * H)
c0 = 10 * Vmax; rho0 = 1000.0
tdamp = 1.0
p0 = c0*c0*rho0

# Reynolds number and kinematic viscosity
Re = 100; nu = Vmax * Ly/Re

# Numerical setup
nx = 100; dx = Lx/nx
ghost_extent = 5.5 * dx
hdx = 1.2

# adaptive time steps
h0 = hdx * dx
dt_cfl = 0.25 * h0/( c0 + Vmax )
dt_viscous = 0.125 * h0**2/nu
dt_force = 0.25 * np.sqrt(h0/abs(gy))

tf = 5.0
dt = 0.5 * min(dt_cfl, dt_viscous, dt_force)

def create_particles(**kwargs):
    # create all the particles
    _x = np.arange( -ghost_extent, Lx + ghost_extent, dx )
    _y = np.arange( -ghost_extent, Ly, dx )
    x, y = np.meshgrid(_x, _y); x = x.ravel(); y = y.ravel()

    # sort out the fluid and the solid
    indices = []
    for i in range(x.size):
        if ( (x[i] > 0.0) and (x[i] < Lx) ):
            if ( (y[i] > 0.0) and (y[i] < H) ):
                indices.append(i)

    # create the arrays
    solid = get_particle_array(name='solid', x=x, y=y)

    # remove the fluid particles from the solid
    fluid = solid.extract_particles(indices); fluid.set_name('fluid')
    solid.remove_particles(indices)

    print "Hydrostatic tank :: nfluid = %d, nsolid=%d, dt = %g"%(
        fluid.get_number_of_particles(),
        solid.get_number_of_particles(), dt)

    # add requisite properties to the arrays:
    # particle volume
    fluid.add_property('V')
    solid.add_property('V' )

    # advection velocities and accelerations
    for name in ('uhat', 'vhat', 'auhat', 'avhat', 'au', 'av', 'aw'):
        fluid.add_property(name)

    # kernel summation correction for the solid
    solid.add_property('wij')

    # imposed velocity on the solid
    solid.add_property('u0')
    solid.add_property('v0')

    # magnitude of velocity
    fluid.add_property('vmag')

    # setup the particle properties
    volume = dx * dx
    
    # mass is set to get the reference density of rho0
    fluid.m[:] = volume * rho0
    solid.m[:] = volume * rho0

    # volume is set as dx^2
    fluid.V[:] = 1./volume
    solid.V[:] = 1./volume

    # smoothing lengths
    fluid.h[:] = hdx * dx
    solid.h[:] = hdx * dx

    # return the particle list
    return [fluid, solid]

# Create the application.
app = Application()

# Create the kernel
kernel = Gaussian(dim=2)

integrator = Integrator(fluid=TransportVelocityStep())

# Create a solver.
solver = Solver(kernel=kernel, dim=2, integrator=integrator, tdamp=tdamp)

# Setup default parameters.
solver.set_time_step(dt)
solver.set_final_time(tf)

equations = [

    # Summation density for the fluid phase
    Group(
        equations=[
            DensitySummation(
                dest='fluid', sources=['fluid','solid']),
            ]),

    # boundary conditions for the solid wall
    Group(
        equations=[
            SolidWallBC(
                dest='solid', sources=['fluid',], gy=gy, rho0=rho0, p0=p0),
            ]),

    # acceleration equation
    Group(
        equations=[
            StateEquation(dest='fluid', sources=None, b=1.0, rho0=rho0, p0=p0),

            BodyForce(dest='fluid', sources=None, fy=gy),

            MomentumEquation(
                dest='fluid', sources=['fluid', 'solid'], nu=nu),

            ArtificialStress(dest='fluid', sources=['fluid',])

            ]),
    ]

# Setup the application and solver.  This also generates the particles.
app.setup(solver=solver, equations=equations,
          particle_factory=create_particles)

app.run()
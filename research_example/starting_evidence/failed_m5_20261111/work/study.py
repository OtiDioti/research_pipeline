import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,json,platform
import numpy as np
import scipy
from scipy.linalg import eigh,solve
from pathlib import Path

def calc(p,N,F,L=None):
 L=p['L_nm'] if L is None else L
 a=p['alpha0_meV_nm2'];g1,g2,g3=p['gamma'];Delta=p['Delta_meV']
 x=p['x_Ge_strain'];aGe=p['lattice_Ge_A'];ax=p['lattice_Si_A']+(aGe-p['lattice_Si_A'])*x
 ep=(aGe-ax)/ax;ez=-2*p['c12_GPa']/p['c11_GPa']*ep;Q=-p['b_meV']*(ep-ez)
 n=np.arange(1,N+1);m=n[:,None];nn=n[None,:]
 k2=np.diag((np.pi*n/L)**2)
 # exact sine-basis z and derivative integrals
 z=np.eye(N)*L/2
 mask=((m+nn)%2==1)
 z[mask]=(-8*L*m*nn/(np.pi**2*(m*m-nn*nn)**2+np.eye(N)))[mask]
 D=np.zeros((N,N));D[mask]=(4*m*nn/(L*(m*m-nn*nn)+np.eye(N)))[mask]
 V=F*(z-L*np.eye(N)/2)
 HL=a*(g1+2*g2)*k2+V-Q*np.eye(N)
 HS=a*g1*k2+V+Delta*np.eye(N)
 CT=-2*np.sqrt(2)*a*g2*k2;CE=np.sqrt(2)*Q*np.eye(N);C=CT+CE
 H=np.block([[HL,C],[C,HS]])
 es,vs=eigh(H,subset_by_index=[0,1]);E=es[0];l=vs[:N,0];s=vs[N:,0]
 st=solve(HS-E*np.eye(N),-CT@l,assume_a='sym');se=solve(HS-E*np.eye(N),-CE@l,assume_a='sym')
 factor=6*np.sqrt(2)*a*g3
 at=float(factor*l@D@st);ae=float(factor*l@D@se);alpha=float(factor*l@D@s)
 # full four-component LH/SO partners, derivative matrix, finite-k splitting check
 Hminus=np.block([[HL,-C],[-C,HS]])
 Hzero=np.block([[H,np.zeros_like(H)],[np.zeros_like(H),Hminus]])
 S=-1j*2*np.sqrt(3)*a*g3*D
 W=np.block([[np.zeros_like(D),-np.sqrt(1.5)*S],[-np.sqrt(1.5)*S,np.zeros_like(D)]])
 H1=np.block([[np.zeros_like(H),W],[W.conj().T,np.zeros_like(H)]])
 splits=[]
 for k in [1e-5,3e-6]:
  ev=eigh(Hzero+k*H1,subset_by_index=[0,1],eigvals_only=True)
  splits.append(float((ev[1]-ev[0])/(2*k)))
 HH=a*(g1-2*g2)*k2+V+Q*np.eye(N)
 eh=eigh(HH,subset_by_index=[0,0],eigvals_only=True)[0]
 return dict(N=N,F_hole_mV_nm=F,L_nm=L,Qepsilon_meV=Q,strain_parallel=ep,E0_meV=float(E),HH_minus_LH_meV=float(eh-E),SO_weight=float(s@s),alpha_total_meV_nm=alpha,alpha_kinetic_source_meV_nm=at,alpha_strain_source_meV_nm=ae,alpha_kappa_meV_nm=0.,alpha_q_meV_nm=0.,signed_kinetic_fraction=at/alpha if abs(alpha)>1e-10 else None,signed_strain_fraction=ae/alpha if abs(alpha)>1e-10 else None,sum_error_meV_nm=float(at+ae-alpha),SO_reconstruction_error=float(np.linalg.norm(st+se-s)),finite_k_abs_alpha_meV_nm=splits)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--params',default='/project/work/parameters.json');ap.add_argument('--out',default='/project/work/results.json');args=ap.parse_args();p=json.load(open(args.params))
 result={'model':'homogeneous Ge-parameter tensile infinite box; not finite SiGe manuscript reproduction','reference':[calc(p,n,1.) for n in [20,40,60,80]],'field_variation':[calc(p,60,f) for f in [-1.,0.,.5,1.5]],'width_variation':[calc(p,60,1.,L) for L in [20.,30.]],'large_gap_limit':calc({**p,'Delta_meV':290000.},60,1.)}
 Path(args.out).parent.mkdir(parents=True,exist_ok=True);Path(args.out).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
if __name__=='__main__': main()

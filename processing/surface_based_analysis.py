"""
This script does 2 things:
1. Freesurfer segmentation
2. project the coregistered fMRI images to the surface:
the surface is the grey-white matter interface of the subject

The purpose is to perform proper group analysis on the surface on fsaverage,
and use existing  atlases on the surface.

Author: Bertrand Thirion, Isabelle Courcol, 2013 -- 2016

Note
----
First run: export SUBJECTS_DIR=''
"""
import os
import glob
import commands
from nipype.caching import Memory
from joblib import Parallel, delayed

from nipype.interfaces.freesurfer import ReconAll, BBRegister


work_dir = '/neurospin/ibc/derivatives'
subjects = ['sub-%02d' % i for i in [1, 2, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14]]

# Step 1: Perform recon-all
os.environ['SUBJECTS_DIR'] = ''

def recon_all(work_dir, subject):
    # create directories in output_dir
    mem = Memory(base_dir='/data/cache_dir')
    if 1:
        # high-resolution T1
        anat_img = glob.glob(os.path.join(
            work_dir, subject, 'ses-*/anat/sub-*_ses-*_acq-highres_T1w.nii'))[0]
        t1_dir = os.path.dirname(anat_img)
    else:
        # low-resolution T1
        subject_dir = os.path.join(work_dir, subject, 'ses-00')
        t1_dir = os.path.join(subject_dir, 'anat')
        anat_img = glob.glob(os.path.join(t1_dir, '%s_ses-00_T1w.nii*' % subject))[0]
    reconall = mem.cache(ReconAll)
    reconall(subject_id=subject,
                      directive='all',
                      subjects_dir=t1_dir,
                      T1_files=anat_img)

"""    
Parallel(n_jobs=3)(delayed(recon_all)(work_dir, subject)
                        for subject in subjects)
"""

# Step 2: Perform the projection
def project_volume(work_dir, subject, do_bbr=True):
    t1_dir = os.path.join(work_dir, subject, 'ses-00', 'anat')
    for idx in range(12):
        subject_dir = os.path.join(work_dir, subject, 'ses-%02d' % idx)
        if not os.path.exists(subject_dir):
            continue
        fmri_dir = os.path.join(subject_dir, 'func')
        fs_dir = os.path.join(subject_dir, 'freesurfer')
        fmri_images = glob.glob(os.path.join(fmri_dir, 'rdc*.nii.gz'))
        
        # --------------------------------------------------------------------
        # run the projection using freesurfer
        os.environ['SUBJECTS_DIR'] = t1_dir
        if not os.path.exists(fs_dir):
            os.mkdir(fs_dir)

        # take the fMRI series
        print("fmri_images", fmri_images)
        for fmri_session in fmri_images:
            basename = os.path.basename(fmri_session).split('.')[0]
            print (basename)
            # output names
            # the .gii files will be put in the same directory as the input fMRI
            left_fmri_tex = os.path.join(fs_dir, basename + '_lh.gii')
            right_fmri_tex = os.path.join(fs_dir, basename + '_rh.gii')
            if do_bbr:
                # use BBR registration to finesse the coregistration
                bbreg = BBRegister(subject_id=subject, source_file=fmri_session,
                                   init='header', contrast_type='t2')
                bbreg.run()
    
            # run freesrufer command for projection
            regheader = os.path.join(fmri_dir, basename + '_bbreg_%s.dat' % subject)
            print(commands.getoutput(
                '$FREESURFER_HOME/bin/mri_vol2surf --src %s --o %s '\
                '--out_type gii --srcreg %s --hemi lh --projfrac-avg 0 2 0.1'
                % (fmri_session, left_fmri_tex, regheader)))

            print(commands.getoutput(
                '$FREESURFER_HOME/bin/mri_vol2surf --src %s --o %s '\
                '--out_type gii --srcreg %s --hemi rh --projfrac-avg 0 2 0.1'
                % (fmri_session, right_fmri_tex, regheader)))

            # resample to fsaverage
            left_fsaverage_fmri_tex = os.path.join(
                fs_dir, basename + '_fsaverage_lh.gii')
            right_fsaverage_fmri_tex = os.path.join(
                fs_dir, basename + '_fsaverage_rh.gii')
        
            print(commands.getoutput(
                '$FREESURFER_HOME/bin/mri_surf2surf --srcsubject %s --srcsurfval '\
                '%s --trgsurfval %s --trgsubject ico --trgicoorder 7 '\
                '--hemi lh --nsmooth-out 5' %
                (subject, left_fmri_tex, left_fsaverage_fmri_tex)))
            print(commands.getoutput(
                '$FREESURFER_HOME/bin/mri_surf2surf --srcsubject %s --srcsurfval '\
                '%s --trgsubject ico --trgicoorder 7 --trgsurfval %s '\
                '--hemi rh --nsmooth-out 5' %
                (subject, right_fmri_tex, right_fsaverage_fmri_tex)))

Parallel(n_jobs=6)(
    delayed(project_volume)(work_dir, subject, do_bbr=False)
    for subject in subjects)

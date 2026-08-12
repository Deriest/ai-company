/**
 * After-pack script to fix symlinks in AppImage
 * electron-builder doesn't follow symlinks by default, so we need to
 * flatten the Python venv structure after building
 */

const fs = require('fs');
const path = require('path');

module.exports = async (context) => {
  const { appOutDir } = context;
  
  console.log('🔧 Fixing symlinks in python-linux bundle...');
  
  const pythonLinuxPath = path.join(appOutDir, 'python-linux');
  
  if (!fs.existsSync(pythonLinuxPath)) {
    console.log('⚠️  python-linux not found, skipping symlink fix');
    return;
  }
  
  // Find and resolve all symlinks
  function resolveSymlinks(dir) {
    const items = fs.readdirSync(dir);
    
    for (const item of items) {
      const fullPath = path.join(dir, item);
      const stat = fs.lstatSync(fullPath);
      
      if (stat.isSymbolicLink()) {
        const target = fs.readlinkSync(fullPath);
        
        // Resolve relative symlinks
        let resolvedTarget;
        if (path.isAbsolute(target)) {
          resolvedTarget = target;
        } else {
          resolvedTarget = path.resolve(dir, target);
        }
        
        console.log(`   Resolving: ${item} → ${resolvedTarget}`);
        
        // Copy actual content instead of symlink
        if (fs.existsSync(resolvedTarget)) {
          try {
            const realStat = fs.statSync(resolvedTarget);
            
            if (realStat.isDirectory()) {
              // Remove symlink directory
              fs.rmSync(fullPath, { recursive: true, force: true });
              
              // Copy entire directory
              fs.cpSync(resolvedTarget, fullPath, { 
                recursive: true,
                dereference: true // Don't copy symlinks, copy actual content
              });
            } else {
              // File symlink - replace with actual file
              fs.rmSync(fullPath, { force: true });
              fs.copyFileSync(resolvedTarget, fullPath);
            }
          } catch (err) {
            console.warn(`   ⚠️  Error resolving ${item}: ${err.message}`);
          }
        }
      } else if (stat.isDirectory()) {
        // Recursively process subdirectories
        resolveSymlinks(fullPath);
      }
    }
  }
  
  resolveSymlinks(pythonLinuxPath);
  
  console.log('✅ Symlink fix complete!');
};

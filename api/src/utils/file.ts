import path from 'path';
import fs from 'fs/promises';
import { createReadStream, createWriteStream } from 'fs';
import { pipeline } from 'stream/promises';
import mimeTypes from 'mime-types';
import fileType from 'file-type';
import sharp from 'sharp';
import { config } from '@/config/index.js';
import { FileUploadError, ValidationError } from './errors.js';
import { integrity } from './crypto.js';

// Supported file types for document processing
export const SUPPORTED_DOCUMENT_TYPES = [
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'text/plain',
  'text/markdown',
  'text/csv',
];

// Supported image types
export const SUPPORTED_IMAGE_TYPES = [
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
  'image/bmp',
  'image/tiff',
];

// Maximum file sizes by type
export const MAX_FILE_SIZES = {
  document: 100 * 1024 * 1024, // 100MB
  image: 50 * 1024 * 1024,     // 50MB
  default: 10 * 1024 * 1024,   // 10MB
};

// File validation result
export interface FileValidationResult {
  valid: boolean;
  errors: string[];
  detectedMimeType?: string;
  fileSize?: number;
}

// File metadata
export interface FileMetadata {
  filename: string;
  originalName: string;
  mimeType: string;
  size: number;
  extension: string;
  checksum: string;
  uploadedAt: Date;
  path: string;
}

// File operations
export const fileOps = {
  // Validate file
  async validateFile(
    buffer: Buffer,
    filename: string,
    allowedTypes: string[] = [...SUPPORTED_DOCUMENT_TYPES, ...SUPPORTED_IMAGE_TYPES]
  ): Promise<FileValidationResult> {
    const errors: string[] = [];
    
    // Check file size
    if (buffer.length === 0) {
      errors.push('File is empty');
    } else if (buffer.length > config.UPLOAD_MAX_FILE_SIZE) {
      errors.push(`File size exceeds maximum allowed size (${Math.round(config.UPLOAD_MAX_FILE_SIZE / 1024 / 1024)}MB)`);
    }
    
    // Detect actual file type
    const detectedType = await fileType.fromBuffer(buffer);
    const detectedMimeType = detectedType?.mime;
    
    // Check MIME type
    if (!detectedMimeType) {
      // Try to infer from extension as fallback
      const inferredMimeType = mimeTypes.lookup(filename);
      if (!inferredMimeType || !allowedTypes.includes(inferredMimeType)) {
        errors.push('Unable to determine file type or unsupported file type');
      }
    } else if (!allowedTypes.includes(detectedMimeType)) {
      errors.push(`File type ${detectedMimeType} is not supported`);
    }
    
    // Check filename
    if (!filename || filename.trim().length === 0) {
      errors.push('Filename is required');
    } else if (filename.includes('..') || filename.includes('/') || filename.includes('\\')) {
      errors.push('Invalid filename');
    }
    
    return {
      valid: errors.length === 0,
      errors,
      detectedMimeType,
      fileSize: buffer.length,
    };
  },

  // Generate safe filename
  generateSafeFilename(originalName: string): string {
    const timestamp = Date.now();
    const randomSuffix = Math.random().toString(36).substring(2, 8);
    const extension = path.extname(originalName);
    const baseName = path.basename(originalName, extension)
      .replace(/[^a-zA-Z0-9-_]/g, '_')
      .substring(0, 50);
    
    return `${timestamp}_${randomSuffix}_${baseName}${extension}`;
  },

  // Save uploaded file
  async saveFile(buffer: Buffer, originalName: string, subDir = ''): Promise<FileMetadata> {
    const filename = fileOps.generateSafeFilename(originalName);
    const uploadDir = path.join(config.TEMP_DIR, subDir);
    const filePath = path.join(uploadDir, filename);
    
    // Ensure directory exists
    await fs.mkdir(uploadDir, { recursive: true });
    
    // Write file
    await fs.writeFile(filePath, buffer);
    
    // Calculate checksum
    const checksum = integrity.calculateBufferChecksum(buffer);
    
    // Get file stats
    const stats = await fs.stat(filePath);
    const mimeType = mimeTypes.lookup(filename) || 'application/octet-stream';
    
    return {
      filename,
      originalName,
      mimeType,
      size: stats.size,
      extension: path.extname(filename).toLowerCase(),
      checksum,
      uploadedAt: new Date(),
      path: filePath,
    };
  },

  // Move file to permanent location
  async moveFile(tempPath: string, permanentPath: string): Promise<void> {
    const permanentDir = path.dirname(permanentPath);
    await fs.mkdir(permanentDir, { recursive: true });
    await fs.rename(tempPath, permanentPath);
  },

  // Delete file
  async deleteFile(filePath: string): Promise<boolean> {
    try {
      await fs.unlink(filePath);
      return true;
    } catch (error) {
      return false;
    }
  },

  // Check if file exists
  async fileExists(filePath: string): Promise<boolean> {
    try {
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  },

  // Get file info
  async getFileInfo(filePath: string): Promise<FileMetadata | null> {
    try {
      const stats = await fs.stat(filePath);
      const filename = path.basename(filePath);
      const mimeType = mimeTypes.lookup(filename) || 'application/octet-stream';
      
      return {
        filename,
        originalName: filename,
        mimeType,
        size: stats.size,
        extension: path.extname(filename).toLowerCase(),
        checksum: await integrity.calculateChecksum(filePath),
        uploadedAt: stats.birthtime,
        path: filePath,
      };
    } catch {
      return null;
    }
  },

  // Copy file
  async copyFile(sourcePath: string, destPath: string): Promise<void> {
    const destDir = path.dirname(destPath);
    await fs.mkdir(destDir, { recursive: true });
    await fs.copyFile(sourcePath, destPath);
  },

  // Stream file
  createReadStream(filePath: string) {
    return createReadStream(filePath);
  },

  // Get file size
  async getFileSize(filePath: string): Promise<number> {
    const stats = await fs.stat(filePath);
    return stats.size;
  },
};

// Image processing utilities
export const imageOps = {
  // Validate image
  async validateImage(buffer: Buffer): Promise<FileValidationResult> {
    const result = await fileOps.validateFile(buffer, 'image.jpg', SUPPORTED_IMAGE_TYPES);
    
    // Additional image-specific validations
    try {
      const metadata = await sharp(buffer).metadata();
      
      if (!metadata.width || !metadata.height) {
        result.errors.push('Invalid image format');
      }
      
      // Check dimensions (max 10000x10000)
      if (metadata.width && metadata.width > 10000) {
        result.errors.push('Image width exceeds maximum allowed (10000px)');
      }
      
      if (metadata.height && metadata.height > 10000) {
        result.errors.push('Image height exceeds maximum allowed (10000px)');
      }
      
    } catch (error) {
      result.errors.push('Unable to process image file');
    }
    
    result.valid = result.errors.length === 0;
    return result;
  },

  // Resize image
  async resizeImage(
    inputBuffer: Buffer,
    options: { width?: number; height?: number; fit?: 'cover' | 'contain' | 'fill' }
  ): Promise<Buffer> {
    let transform = sharp(inputBuffer);
    
    if (options.width || options.height) {
      transform = transform.resize({
        width: options.width,
        height: options.height,
        fit: options.fit || 'contain',
        background: { r: 255, g: 255, b: 255, alpha: 1 },
      });
    }
    
    return await transform.toBuffer();
  },

  // Convert image format
  async convertFormat(inputBuffer: Buffer, format: 'jpeg' | 'png' | 'webp'): Promise<Buffer> {
    const transform = sharp(inputBuffer);
    
    switch (format) {
      case 'jpeg':
        return await transform.jpeg({ quality: 90 }).toBuffer();
      case 'png':
        return await transform.png({ compressionLevel: 6 }).toBuffer();
      case 'webp':
        return await transform.webp({ quality: 90 }).toBuffer();
      default:
        throw new ValidationError(`Unsupported image format: ${format}`);
    }
  },

  // Generate thumbnail
  async generateThumbnail(inputBuffer: Buffer, size = 150): Promise<Buffer> {
    return await sharp(inputBuffer)
      .resize(size, size, { fit: 'cover' })
      .jpeg({ quality: 80 })
      .toBuffer();
  },

  // Extract EXIF data
  async extractMetadata(inputBuffer: Buffer) {
    const metadata = await sharp(inputBuffer).metadata();
    return {
      width: metadata.width,
      height: metadata.height,
      format: metadata.format,
      space: metadata.space,
      channels: metadata.channels,
      depth: metadata.depth,
      density: metadata.density,
      hasProfile: metadata.hasProfile,
      hasAlpha: metadata.hasAlpha,
      exif: metadata.exif,
      icc: metadata.icc,
    };
  },
};

// Directory utilities
export const directoryOps = {
  // Create directory if not exists
  async ensureDir(dirPath: string): Promise<void> {
    await fs.mkdir(dirPath, { recursive: true });
  },

  // Clean old files from directory
  async cleanupOldFiles(dirPath: string, maxAgeMs: number): Promise<number> {
    let cleanedCount = 0;
    const cutoffTime = Date.now() - maxAgeMs;
    
    try {
      const files = await fs.readdir(dirPath);
      
      for (const file of files) {
        const filePath = path.join(dirPath, file);
        const stats = await fs.stat(filePath);
        
        if (stats.mtimeMs < cutoffTime) {
          await fs.unlink(filePath);
          cleanedCount++;
        }
      }
    } catch (error) {
      // Directory might not exist, ignore
    }
    
    return cleanedCount;
  },

  // Get directory size
  async getDirectorySize(dirPath: string): Promise<number> {
    let totalSize = 0;
    
    try {
      const files = await fs.readdir(dirPath, { withFileTypes: true });
      
      for (const file of files) {
        const filePath = path.join(dirPath, file.name);
        
        if (file.isFile()) {
          const stats = await fs.stat(filePath);
          totalSize += stats.size;
        } else if (file.isDirectory()) {
          totalSize += await directoryOps.getDirectorySize(filePath);
        }
      }
    } catch (error) {
      // Directory might not exist, return 0
    }
    
    return totalSize;
  },

  // List files with metadata
  async listFiles(dirPath: string, recursive = false): Promise<FileMetadata[]> {
    const files: FileMetadata[] = [];
    
    try {
      const entries = await fs.readdir(dirPath, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(dirPath, entry.name);
        
        if (entry.isFile()) {
          const fileInfo = await fileOps.getFileInfo(fullPath);
          if (fileInfo) {
            files.push(fileInfo);
          }
        } else if (entry.isDirectory() && recursive) {
          const subFiles = await directoryOps.listFiles(fullPath, true);
          files.push(...subFiles);
        }
      }
    } catch (error) {
      // Directory might not exist, return empty array
    }
    
    return files;
  },
};

// Cleanup utilities
export const cleanup = {
  // Schedule cleanup task
  scheduleCleanup(intervalMs: number = config.CLEANUP_INTERVAL_MS): NodeJS.Timer {
    return setInterval(async () => {
      try {
        const cleaned = await directoryOps.cleanupOldFiles(
          config.TEMP_DIR,
          24 * 60 * 60 * 1000 // 24 hours
        );
        
        if (cleaned > 0) {
          console.log(`Cleaned up ${cleaned} temporary files`);
        }
      } catch (error) {
        console.error('Cleanup task failed:', error);
      }
    }, intervalMs);
  },

  // Manual cleanup
  async runCleanup(): Promise<{ tempFiles: number; totalSize: number }> {
    const tempFiles = await directoryOps.cleanupOldFiles(
      config.TEMP_DIR,
      24 * 60 * 60 * 1000 // 24 hours
    );
    
    const totalSize = await directoryOps.getDirectorySize(config.TEMP_DIR);
    
    return { tempFiles, totalSize };
  },
};
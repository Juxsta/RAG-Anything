import { FastifyInstance, FastifyPluginCallback } from 'fastify';
import fp from 'fastify-plugin';
import { Type } from '@sinclair/typebox';
import { SystemConfigSchema, ConfigUpdateRequestSchema } from '@/types/config.js';
import { ConfigurationError, ValidationError } from '@/utils/errors.js';
import { createAuthorizationMiddleware } from '@/middleware/auth.js';

/**
 * Configuration management routes
 */
export const configRoutes: FastifyPluginCallback = fp(async (fastify: FastifyInstance) => {
  
  // Admin-only middleware
  await fastify.register(createAuthorizationMiddleware(['admin']));

  /**
   * Get current configuration
   * GET /api/v1/config
   */
  fastify.get('/', {
    schema: {
      description: 'Retrieve the current system configuration',
      tags: ['Configuration'],
      security: [{ BearerAuth: [] }],
      response: {
        200: {
          description: 'Configuration retrieved successfully',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: true },
            data: SystemConfigSchema,
            meta: {
              type: 'object',
              properties: {
                request_id: { type: 'string' },
                timestamp: { type: 'string' },
              },
            },
          },
        },
      },
    },
  }, async (request, reply) => {
    try {
      // TODO: Get actual configuration from RAG-Anything
      const currentConfig = {
        directory: {
          working_dir: './rag_storage',
          parser_output_dir: './output',
        },
        parsing: {
          parser: 'mineru' as const,
          parse_method: 'auto' as const,
          display_content_stats: true,
        },
        multimodal_processing: {
          enable_image_processing: true,
          enable_table_processing: true,
          enable_equation_processing: true,
        },
        context_extraction: {
          context_window: 1,
          context_mode: 'page' as const,
          max_context_tokens: 2000,
        },
        batch_processing: {
          max_concurrent_files: 2,
          supported_file_extensions: ['.pdf', '.docx', '.pptx', '.txt', '.md'],
          recursive_folder_processing: true,
        },
      };
      
      return reply.sendSuccess(currentConfig);
      
    } catch (error) {
      throw new ConfigurationError('Failed to retrieve configuration');
    }
  });

  /**
   * Update configuration
   * PATCH /api/v1/config
   */
  fastify.patch('/', {
    schema: {
      description: 'Update system configuration dynamically',
      tags: ['Configuration'],
      security: [{ BearerAuth: [] }],
      body: ConfigUpdateRequestSchema,
      response: {
        200: {
          description: 'Configuration updated successfully',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: true },
            data: {
              type: 'object',
              properties: {
                updated_fields: {
                  type: 'array',
                  items: { type: 'string' },
                },
                warnings: {
                  type: 'array',
                  items: { type: 'string' },
                },
                restart_required: { type: 'boolean' },
              },
            },
          },
        },
      },
    },
  }, async (request, reply) => {
    const updates = request.body;
    
    try {
      // Validate configuration updates
      const updatedFields: string[] = [];
      const warnings: string[] = [];
      let restartRequired = false;
      
      // Process directory updates
      if (updates.directory) {
        if (updates.directory.working_dir) {
          updatedFields.push('directory.working_dir');
          warnings.push('Working directory change requires service restart');
          restartRequired = true;
        }
        if (updates.directory.parser_output_dir) {
          updatedFields.push('directory.parser_output_dir');
        }
      }
      
      // Process parsing updates
      if (updates.parsing) {
        if (updates.parsing.parser) {
          updatedFields.push('parsing.parser');
          warnings.push('Parser change requires processor reinitialization');
        }
        if (updates.parsing.parse_method) {
          updatedFields.push('parsing.parse_method');
        }
        if (updates.parsing.display_content_stats !== undefined) {
          updatedFields.push('parsing.display_content_stats');
        }
      }
      
      // Process multimodal processing updates
      if (updates.multimodal_processing) {
        if (updates.multimodal_processing.enable_image_processing !== undefined) {
          updatedFields.push('multimodal_processing.enable_image_processing');
          warnings.push('Multimodal processor changes require reinitialization');
        }
        if (updates.multimodal_processing.enable_table_processing !== undefined) {
          updatedFields.push('multimodal_processing.enable_table_processing');
        }
        if (updates.multimodal_processing.enable_equation_processing !== undefined) {
          updatedFields.push('multimodal_processing.enable_equation_processing');
        }
      }
      
      // Process context extraction updates
      if (updates.context_extraction) {
        if (updates.context_extraction.context_window) {
          updatedFields.push('context_extraction.context_window');
        }
        if (updates.context_extraction.context_mode) {
          updatedFields.push('context_extraction.context_mode');
        }
        if (updates.context_extraction.max_context_tokens) {
          updatedFields.push('context_extraction.max_context_tokens');
        }
      }
      
      // Process batch processing updates
      if (updates.batch_processing) {
        if (updates.batch_processing.max_concurrent_files) {
          updatedFields.push('batch_processing.max_concurrent_files');
        }
        if (updates.batch_processing.recursive_folder_processing !== undefined) {
          updatedFields.push('batch_processing.recursive_folder_processing');
        }
      }
      
      // TODO: Apply actual configuration changes to RAG-Anything instance
      // await ragAnythingInstance.updateConfig(updates);
      
      const response = {
        updated_fields: updatedFields,
        warnings,
        restart_required: restartRequired,
      };
      
      return reply.sendSuccess(response);
      
    } catch (error) {
      throw new ConfigurationError('Failed to update configuration', {
        error: error.message,
      });
    }
  });

  /**
   * Reset configuration to defaults
   * POST /api/v1/config/reset
   */
  fastify.post('/reset', {
    schema: {
      description: 'Reset all configuration parameters to their default values',
      tags: ['Configuration'],
      security: [{ BearerAuth: [] }],
      response: {
        200: {
          description: 'Configuration reset successfully',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: true },
            data: {
              type: 'object',
              properties: {
                message: { type: 'string' },
                restart_required: { type: 'boolean' },
              },
            },
          },
        },
      },
    },
  }, async (request, reply) => {
    try {
      // TODO: Reset RAG-Anything configuration to defaults
      // await ragAnythingInstance.resetConfig();
      
      const response = {
        message: 'Configuration has been reset to default values',
        restart_required: true,
      };
      
      return reply.sendSuccess(response);
      
    } catch (error) {
      throw new ConfigurationError('Failed to reset configuration');
    }
  });

  /**
   * Get configuration schema
   * GET /api/v1/config/schema
   */
  fastify.get('/schema', {
    schema: {
      description: 'Get configuration schema with validation rules',
      tags: ['Configuration'],
      response: {
        200: {
          description: 'Configuration schema retrieved successfully',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: true },
            data: {
              type: 'object',
              properties: {
                schema: { type: 'object' },
                defaults: { type: 'object' },
                validation_rules: { type: 'object' },
              },
            },
          },
        },
      },
    },
  }, async (request, reply) => {
    try {
      const configSchema = {
        schema: SystemConfigSchema,
        defaults: {
          directory: {
            working_dir: './rag_storage',
            parser_output_dir: './output',
          },
          parsing: {
            parser: 'mineru',
            parse_method: 'auto',
            display_content_stats: true,
          },
          multimodal_processing: {
            enable_image_processing: true,
            enable_table_processing: true,
            enable_equation_processing: true,
          },
          context_extraction: {
            context_window: 1,
            context_mode: 'page',
            max_context_tokens: 2000,
          },
          batch_processing: {
            max_concurrent_files: 2,
            supported_file_extensions: ['.pdf', '.docx', '.pptx', '.txt', '.md'],
            recursive_folder_processing: true,
          },
        },
        validation_rules: {
          'directory.working_dir': 'Must be a valid directory path',
          'parsing.max_concurrent_files': 'Must be between 1 and 10',
          'context_extraction.max_context_tokens': 'Must be between 100 and 8000',
        },
      };
      
      return reply.sendSuccess(configSchema);
      
    } catch (error) {
      throw new ConfigurationError('Failed to retrieve configuration schema');
    }
  });

}, {
  name: 'config-routes',
});
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://saintus-create.github.io',
  base: '/https-leginfo.legislature.ca.gov',
  integrations: [
    starlight({
      title: 'California Legislative Information',
      description: 'A structured, searchable reference to California statutes and legislative data.',
      logo: {
        replacesTitle: true,
        src: './src/assets/ca-mark.svg',
      },
      customCss: ['./src/styles/custom.css'],
      sidebar: [
        {
          label: 'Legislative Information',
          items: [
            { label: 'Overview', slug: 'index' },
            { label: 'Codes', slug: 'codes' },
            { label: 'Search', slug: 'search' },
            { label: 'Data & provenance', slug: 'data' },
          ],
        },
        {
          label: 'Project',
          items: [
            { label: 'Sources', slug: 'sources' },
            { label: 'Technical notes', slug: 'technical' },
          ],
        },
      ],
      editLink: {
        baseUrl: 'https://github.com/saintus-create/https-leginfo.legislature.ca.gov/edit/main/src/content/docs/',
      },
      social: {
        github: 'https://github.com/saintus-create/https-leginfo.legislature.ca.gov',
      },
    }),
  ],
});

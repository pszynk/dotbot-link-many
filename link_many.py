import os
import shutil
import dotbot


class LinkMany(dotbot.Plugin):
    '''
    Symbolically links many dotfiles in directory.
    '''

    _directive = 'link-many'
    _opts = ['path', 'relative', 'force', 'relink', 'create']

    def can_handle(self, directive):
        return directive == self._directive

    def handle(self, directive, data):
        if directive != self._directive:
            raise ValueError('Link cannot handle directive %s' % directive)
        return self._process_links(data)

    def _process_links(self, links):
        success = True
        defaults = {**self._default_opts(), **self._context.defaults().get(self._directive, {})}

        for destination, source in links.items():
            destination = self._expand_path(destination)
            opts = dict(defaults)
            if isinstance(source, dict):
                # extended config
                opts.update(source)
            else:
                opts['path'] = source
            source_path = self._default_source(destination, opts['path'])

            warn_msgs = []
            if not self._exists(source_path):
                warn_msgs.append('Nonexistent source {} -> {}'.format(destination, source_path))
            elif not os.path.isdir(source_path):
                warn_msgs.append('Source must be a directory {} -> {}'.format(destination, source_path))
            elif not os.listdir(source_path):
                warn_msgs.append('Source directory is empty {} -> {}'.format(destination, source_path))
            if warn_msgs:
                for m in warn_msgs:
                    self._log.warning(m)
                success=False
                continue

            create, force, relative, relink = [opts[x] for x in
                                               ['create', 'force', 'relative', 'relink']]

            # try to create destination directory
            if create:
                ok = self._create(destination)
                success &= ok
                if not ok:
                    continue

            # for each file in source directory
            for f in os.listdir(source_path):
                dst, src = [os.path.join(x, f) for x in (destination, source_path)]
                if force or relink:
                    success &= self._delete(src, dst, relative, force)
                success &= self._link(src, dst, relative)

        if success:
            self._log.info('All links have been set up')
        else:
            self._log.error('Some links were not successfully set up')
        return success

    def _default_opts(self):
        opts = {k: False for k in self._opts }
        opts['path'] = None
        return opts

    def _default_source(self, destination, source):
        path = source
        if not path:
            path = os.path.basename(destination)
            if path.startswith('.'):
                path = path[1:]
        return self._expand_path(os.path.join(self._context.base_directory(), path))

    def _expand_path(self, path):
        return os.path.expandvars(os.path.expanduser(path))

    def _is_link(self, path):
        '''
        Returns true if the path is a symbolic link.
        '''
        return os.path.islink(os.path.expanduser(path))

    def _link_destination(self, path):
        '''
        Returns the destination of the symbolic link.
        '''
        return os.readlink(self._expand_path(path))

    def _exists(self, path):
        '''
        Returns true if the path exists.
        '''
        return os.path.exists(self._expand_path(path))

    def _create(self, path):
        if not self._exists(path):
            try:
                os.makedirs(path)
            except OSError:
                self._log.warning('Failed to create directory %s' % path)
                return False
            else:
                self._log.lowinfo('Creating directory %s' % path)
                return True
        return True

    def _delete(self, source, path, relative, force):
        success = True
        if relative:
            source = self._relative_path(source, path)
        if ((self._is_link(path) and self._link_destination(path) != source) or
                (self._exists(path) and not self._is_link(path))):
            removed = False
            try:
                if os.path.islink(path):
                    os.unlink(path)
                    removed = True
                elif force:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                        removed = True
                    else:
                        os.remove(path)
                        removed = True
            except OSError:
                self._log.warning('Failed to remove %s' % path)
                success = False
            else:
                if removed:
                    self._log.lowinfo('Removing %s' % path)
        return success

    def _relative_path(self, source, destination):
        '''
        Returns the relative path to get to the source file from the
        destination file.
        '''
        destination_dir = os.path.dirname(destination)
        return os.path.relpath(source, destination_dir)

    def _link(self, source, link_name, relative):
        '''
        Links link_name to source.

        Returns true if successfully linked files.
        '''
        success = False
        destination = os.path.expanduser(link_name)
        absolute_source = os.path.join(self._context.base_directory(), source)
        if relative:
            source = self._relative_path(absolute_source, destination)
        else:
            source = absolute_source
        if (not self._exists(link_name) and self._is_link(link_name) and
                self._link_destination(link_name) != source):
            self._log.warning('Invalid link %s -> %s' %
                (link_name, self._link_destination(link_name)))
        # we need to use absolute_source below because our cwd is the dotfiles
        # directory, and if source is relative, it will be relative to the
        # destination directory
        elif not self._exists(link_name) and self._exists(absolute_source):
            try:
                os.symlink(source, destination)
            except OSError:
                self._log.warning('Linking failed %s -> %s' % (link_name, source))
            else:
                self._log.lowinfo('Creating link %s -> %s' % (link_name, source))
                success = True
        elif self._exists(link_name) and not self._is_link(link_name):
            self._log.warning(
                '%s already exists but is a regular file or directory' %
                link_name)
        elif self._is_link(link_name) and self._link_destination(link_name) != source:
            self._log.warning('Incorrect link %s -> %s' %
                (link_name, self._link_destination(link_name)))
        # again, we use absolute_source to check for existence
        elif not self._exists(absolute_source):
            if self._is_link(link_name):
                self._log.warning('Nonexistent target %s -> %s' %
                    (link_name, source))
            else:
                self._log.warning('Nonexistent target for %s : %s' %
                    (link_name, source))
        else:
            self._log.lowinfo('Link exists %s -> %s' % (link_name, source))
            success = True
        return success

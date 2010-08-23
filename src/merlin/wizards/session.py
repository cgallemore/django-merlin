from uuid import uuid4

from django.http import *
from django.shortcuts import render_to_response
from django.template.context import RequestContext

from merlin.wizards.utils import *


class SessionWizard(object):
    # TODO: add class documentation
    def __init__(self, steps):
        if not isinstance(steps, list):
            raise TypeError('steps must be an instance of or subclass of list')

        if [step for step in steps if not isinstance(step, Step)]:
            raise TypeError('All steps must be an instance of Step')

        slugs = set([step.slug for step in steps])

        # By putting the slugs into a set the duplicates will be filtered out.
        # If the slug list length does not equal the steps length then there
        # must have been duplicates.
        if len(slugs) != len(steps):
            raise ValueError('Step slugs must be unique.')

        self.id = str(uuid4())
        self.base_steps = steps

    def __call__(self, request, *args, **kwargs):
        """
        Initialize the form list for the session if needed and call the proper
        HTTP method handler.
        """
        self._init_wizard(request)
        slug = kwargs.get('slug', None)

        if not slug:
            steps = self.get_steps(request)
            slug = steps[0].slug

        try:
            method_name = 'process_%s' % request.method
            method = getattr(self, method_name)

            return method(request, slug)

        except AttributeError:
            raise Http404()

    def _init_wizard(self, request):
        """
        Since the SessionWizard is used as the callable for the urlconf there
        will be only one instance of the class created. We need to make sure
        each session has its own copy of the step list to manipulate. This
        way multiple connections will not trample on each others steps.
        """
        if self.id not in request.session:
            request.session[self.id] = WizardState(
                steps=self.base_steps[:], # Copies the list
                current_step=self.base_steps[0],
                form_data={})

    def _get_state(self, request):
        return request.session[self.id]

    def _show_form(self, request, slug, form):
        context = self.process_show_form(request, slug, form)
        step = self._set_current_step(request, slug)

        return self.render_form(request, slug, form, {
            'current_step': step,
            'previous_step': None,
            'next_step': None,
            'url_base': self._get_URL_base(request, slug),
            'extra_context': context
        })

    def _set_current_step(self, request, slug):
        step = self.get_step(request, slug)
        self._get_state(request).current_step = step

        return step

    def _get_URL_base(self, request, slug):
        path = request.path
        index = request.path.find(slug)

        if path.endswith('/'):
            return path[:index]
        else:
            return path[:(index -1)]

    def process_GET(self, request, slug):
        form_data = self.get_cleaned_data(request, slug)
        step = self.get_step(request, slug)

        if form_data:
            form = step.form(initial=form_data)

        else:
            form = step.form()

        return self._show_form(request, slug, form)

    def process_POST(self, request, slug):
        pass

    def get_steps(self, request):
        return self._get_state(request).steps

    def get_step(self, request, slug):
        steps = self.get_steps(request)

        try:
            return [step for step in steps if step.slug == slug][0]

        except IndexError:
            return None

    def get_cleaned_data(self, request, slug):
        return self._get_state(request).data.get(slug, None)

    # METHODS SUBCLASSES MIGHT OVERRIDE IF APPROPRIATE #
    def process_show_form(self, request, slug, form):
        """
        Hook for providing extra context to the rendering of the form.
        """

    def get_template(self, request, slug, form):
        """
        Hook for specifying the path of a template to use for rendering this
        form.
        """
        return ''

    def render_form(self, request, slug, form, context):
        """
        Hook for altering how the form is rendered to the response.
        """
        return render_to_response(self.get_template(request, slug, form),
            context, RequestContext(request))

    def done(self, request):
        """
        Hook for doing something with the validated data. This is responsible
        for the final processing including clearing the session scope of items
        created by this wizard.
        """
        raise NotImplementedError("Your %s class has not defined a done() " + \
                                  "method, which is required." \
                                  % self.__class__.__name__)

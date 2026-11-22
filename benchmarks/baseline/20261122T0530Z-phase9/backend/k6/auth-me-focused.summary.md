# k6 summary

scenario: me

- http_req_blocked: med=0.011, max=0.210, p(90)=0.013, p(95)=0.025, p(99)=0.173, avg=0.021, min=0.003
- http_req_waiting: p(90)=9.734, p(95)=9.911, p(99)=10.052, avg=7.644, min=1.996, med=8.190, max=10.088
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_duration{expected_response:true}: avg=7.799, min=2.038, med=8.443, max=10.292, p(90)=9.902, p(95)=10.055, p(99)=10.245
- http_req_failed: rate=0.000
- iterations: rate=4.788, count=20.000
- http_req_sending: max=0.127, p(90)=0.056, p(95)=0.064, p(99)=0.115, avg=0.045, min=0.012, med=0.040
- vus: min=1.000, max=1.000
- http_req_receiving: p(95)=0.190, p(99)=0.217, avg=0.111, min=0.029, med=0.114, max=0.224, p(90)=0.171
- http_req_connecting: p(99)=0.112, avg=0.007, min=0.000, med=0.000, max=0.139, p(90)=0.000, p(95)=0.007
- http_req_duration: avg=7.799, min=2.038, med=8.443, max=10.292, p(90)=9.902, p(95)=10.055, p(99)=10.245

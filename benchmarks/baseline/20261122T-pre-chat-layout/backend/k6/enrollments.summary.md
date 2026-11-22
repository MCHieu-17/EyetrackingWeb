# k6 summary

scenario: enrollments

- http_req_duration: avg=6.217, min=0.991, med=4.485, max=84.518, p(90)=7.056, p(95)=7.246, p(99)=76.795
- http_req_waiting: avg=6.034, min=0.936, med=4.265, max=84.431, p(90)=6.826, p(95)=7.061, p(99)=76.715
- http_req_blocked: med=0.011, max=0.131, p(90)=0.013, p(95)=0.014, p(99)=0.127, avg=0.013, min=0.003
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_failed: rate=0.000
- vus: max=5.000, min=5.000
- iterations: count=243.000, rate=23.999
- http_req_sending: avg=0.038, min=0.007, med=0.039, max=0.101, p(90)=0.048, p(95)=0.052, p(99)=0.081
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.094, avg=0.002, min=0.000, med=0.000, max=0.096
- http_req_duration{expected_response:true}: avg=6.217, min=0.991, med=4.485, max=84.518, p(90)=7.056, p(95)=7.246, p(99)=76.795
- http_req_receiving: p(99)=0.525, avg=0.145, min=0.007, med=0.124, max=0.673, p(90)=0.230, p(95)=0.348

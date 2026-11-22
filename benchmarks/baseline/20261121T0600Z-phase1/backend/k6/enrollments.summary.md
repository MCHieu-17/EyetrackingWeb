# k6 summary

scenario: enrollments

- http_req_duration{expected_response:true}: avg=7.366, min=0.907, med=6.345, max=66.843, p(90)=10.990, p(95)=11.441, p(99)=50.933
- http_req_receiving: med=0.137, max=1.332, p(90)=0.450, p(95)=0.685, p(99)=1.120, avg=0.197, min=0.011
- iterations: count=242.000, rate=23.988
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_sending: avg=0.047, min=0.005, med=0.040, max=0.485, p(90)=0.053, p(95)=0.070, p(99)=0.438
- http_req_waiting: avg=7.121, min=0.891, med=6.171, max=66.372, p(90)=10.516, p(95)=10.918, p(99)=50.296
- http_req_duration: p(99)=50.933, avg=7.366, min=0.907, med=6.345, max=66.843, p(90)=10.990, p(95)=11.441
- http_req_blocked: p(95)=0.018, p(99)=0.927, avg=0.028, min=0.002, med=0.011, max=0.990, p(90)=0.014
- vus: min=5.000, max=5.000
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.274, avg=0.006, min=0.000, med=0.000, max=0.295
- http_req_failed: rate=0.000
